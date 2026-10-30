"""Watches household.sysml during the CleanWatts mock demo and turns each
save into a list of changes (see MOCK-DEMO.md, "Detecting changes").

Reading a save:

1. reload it with `tools.load_sysml.load` (the real SysML parser, through
   the Java exporter, a few seconds), from a copy of the saved text so the
   text and the loaded model always match;
2. read `Main`: the household and the grid (parts owned by `Main`), the PV,
   battery and devices (parts nested in the household), each with its part
   def and configured values, and `batteryControl`'s state def;
3. validate: the exporter reports success and `load` raises nothing even for
   broken input (an empty value, an unresolved part def), so everything read
   is checked here; any problem rejects the whole save;
4. compare with the previous accepted save and produce change objects.

Only these edits are supported: `Real` values of existing parts, adding or
removing devices inside the household, and switching `batteryControl`'s
algorithm. Changes outside the `Main` package (part defs, state machines)
are rejected; comments and whitespace don't count as changes.
"""
import os
import queue
import re
import tempfile
import threading
from dataclasses import dataclass, field
from typing import Optional, Union

from languages.sysmlv2 import syntax
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.controllers import CONTROLLERS
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.simulation import (
    PART_CLASSES, MockDevice,
)
from tools.load_sysml import load

POLL_INTERVAL_SECONDS = 0.5

STATE_USAGE_NAME = "batteryControl"

# Part defs by role. Device part defs come from the simulation, so the two
# can't disagree about what can be added and removed.
DEVICE_PART_DEFS = frozenset(name for name, klass in PART_CLASSES.items() if issubclass(klass, MockDevice))
IN_HOUSEHOLD_SINGLE_PART_DEFS = ("PV", "Battery")


# --- Changes ---------------------------------------------------------------

@dataclass(frozen=True)
class ValueChanged:
    part: str
    attribute: str
    old: float
    new: float

    def describe(self) -> str:
        return f"{_short(self.part)}.{self.attribute} {self.old:g} -> {self.new:g}"


@dataclass(frozen=True)
class PartAdded:
    part: str
    part_def: str
    values: dict

    def describe(self) -> str:
        return f"+ {_short(self.part)} ({self.part_def})"


@dataclass(frozen=True)
class PartRemoved:
    part: str

    def describe(self) -> str:
        return f"- {_short(self.part)}"


@dataclass(frozen=True)
class AlgorithmChanged:
    old: Optional[str]  # None on the first load
    new: str

    def describe(self) -> str:
        return f"algorithm: {self.new}"


Change = Union[ValueChanged, PartAdded, PartRemoved, AlgorithmChanged]


def _short(qualified_name: str) -> str:
    return qualified_name.rsplit("::", 1)[-1]


# --- What a save contains --------------------------------------------------

class ModelRejected(Exception):
    """A save that can't be applied; `reasons` says why, one line each."""

    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class PartState:
    part_def: str
    values: dict  # configured attribute name -> float


@dataclass(frozen=True)
class ModelState:
    """What the demo uses from one accepted save."""
    parts: dict          # qualified name -> PartState, household first, then its parts, then the grid
    algorithm: str       # batteryControl's state def
    household: str       # qualified names of the parts bound to the algorithm
    battery: str
    pv: str
    grid: str
    definitions: str     # everything outside `package Main`, without comments and whitespace


def read_model_text(text: str) -> ModelState:
    """Loads `text` (the content of a .sysml file) and reads it. Raises
    `ModelRejected` if it can't be used.
    """
    handle, path = tempfile.mkstemp(suffix=".sysml")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(text)
        try:
            resource = load(path, keep_xmi=False)
        except RuntimeError as error:  # the exporter failed outright
            raise ModelRejected([str(error)]) from error
    finally:
        os.remove(path)
    return _read_main(resource.contents[0], _definitions(text))


def _members(element) -> list:
    """The elements `element` owns through its memberships (package members,
    a part's features), in declaration order.
    """
    return [member
            for relationship in element.ownedRelationship
            if isinstance(relationship, syntax.OwningMembership)
            for member in relationship.ownedRelatedElement]


def _part_def(part) -> Optional[str]:
    type_node = syntax._feature_type(part)
    return getattr(type_node, "declaredName", None)


def _read_values(part, qualified_name: str, part_def: str, reasons: list[str]) -> dict:
    """The part's configured values as floats, checked against the
    simulation's configured attributes for `part_def`.
    """
    values, invalid = {}, set()
    for redefinition in syntax._owned_attribute_redefinitions(part, qualified_name):
        value = redefinition.value
        scalar_type = getattr(getattr(value, "scalar_type", None), "name", None)
        if type(value).__name__ != "LiteralValue" or scalar_type != "REAL":
            reasons.append(f"{qualified_name}.{redefinition.name}: not a Real number "
                           f"(write it with a decimal point, e.g. 12.0)")
            invalid.add(redefinition.name)
            continue
        values[redefinition.name] = float(value.el)

    for member in _members(part):
        if isinstance(member, syntax.AttributeUsage) and syntax._redefined_feature(member) is None:
            if member.declaredName is None:  # `:>> name` whose name didn't resolve
                reasons.append(f"{qualified_name}: an attribute redefinition doesn't match any "
                               f"attribute of {part_def} (misspelled?)")
            else:
                reasons.append(f"{qualified_name}: attribute {member.declaredName!r} doesn't redefine "
                               f"an attribute of {part_def} (missing ':>>'?)")

    configured = set(PART_CLASSES[part_def].configured)
    for name in sorted(set(values) - configured):
        reasons.append(f"{qualified_name}.{name}: not a configured attribute of {part_def}")
    for name in sorted(configured - set(values) - invalid):
        reasons.append(f"{qualified_name}: {name} is not set")
    return values


def _read_main(root, definitions: str) -> ModelState:
    reasons: list[str] = []

    mains = [element for element in root.eAllContents()
             if isinstance(element, syntax.Package) and element.declaredName == "Main"]
    if len(mains) != 1:
        raise ModelRejected([f"expected one package Main, found {len(mains)}"])
    main = mains[0]

    households, grids, state_usages = [], [], []
    for member in _members(main):
        if isinstance(member, syntax.StateUsage):
            state_usages.append(member)
        elif isinstance(member, syntax.PartUsage):
            part_def = _part_def(member)
            if part_def == "Household":
                households.append(member)
            elif part_def == "Grid":
                grids.append(member)
            elif part_def is None:
                reasons.append(f"Main::{member.declaredName}: unknown part def")
            elif part_def in PART_CLASSES:
                reasons.append(f"Main::{member.declaredName}: a {part_def} must be inside the household")
            else:
                reasons.append(f"Main::{member.declaredName}: part def {part_def} isn't supported")
        elif not isinstance(member, syntax.Comment):
            reasons.append(f"Main: {type(member).__name__} {getattr(member, 'declaredName', '')!r} "
                           f"isn't supported in the demo")

    if len(households) != 1:
        reasons.append(f"Main needs exactly one Household part, found {len(households)}")
    if len(grids) != 1:
        reasons.append(f"Main needs exactly one Grid part, found {len(grids)}")
    if [usage.declaredName for usage in state_usages] != [STATE_USAGE_NAME]:
        reasons.append(f"Main needs exactly one state usage, {STATE_USAGE_NAME}, "
                       f"found {[usage.declaredName for usage in state_usages]}")
    if reasons:
        raise ModelRejected(reasons)

    household, grid, state_usage = households[0], grids[0], state_usages[0]
    algorithm = _part_def(state_usage)
    if algorithm not in CONTROLLERS:
        shown = "doesn't resolve (misspelled?)" if algorithm is None else f"{algorithm!r} isn't supported"
        reasons.append(f"Main::{STATE_USAGE_NAME}: the algorithm {shown}, "
                       f"expected one of {sorted(CONTROLLERS)}")

    parts: dict[str, PartState] = {}
    household_name = syntax.qualified_name(household)
    parts[household_name] = PartState("Household", _read_values(household, household_name, "Household", reasons))

    singles = {part_def: [] for part_def in IN_HOUSEHOLD_SINGLE_PART_DEFS}
    for member in _members(household):
        if not isinstance(member, syntax.PartUsage):
            continue
        name = syntax.qualified_name(member)
        part_def = _part_def(member)
        if part_def is None:
            reasons.append(f"{name}: unknown part def")
            continue
        if part_def not in DEVICE_PART_DEFS and part_def not in IN_HOUSEHOLD_SINGLE_PART_DEFS:
            reasons.append(f"{name}: a {part_def} can't be inside the household")
            continue
        if any(isinstance(nested, syntax.PartUsage) for nested in _members(member)):
            reasons.append(f"{name}: parts inside a {part_def} aren't supported")
        if part_def in singles:
            singles[part_def].append(name)
        parts[name] = PartState(part_def, _read_values(member, name, part_def, reasons))

    for part_def, names in singles.items():
        if len(names) != 1:
            reasons.append(f"{household_name} needs exactly one {part_def}, found {len(names)}")

    grid_name = syntax.qualified_name(grid)
    parts[grid_name] = PartState("Grid", _read_values(grid, grid_name, "Grid", reasons))

    if reasons:
        raise ModelRejected(reasons)
    return ModelState(parts=parts, algorithm=algorithm, household=household_name,
                      battery=singles["Battery"][0], pv=singles["PV"][0], grid=grid_name,
                      definitions=definitions)


def _definitions(text: str) -> str:
    """`text` without comments, without the `package Main { ... }` block, and
    with whitespace collapsed: what must stay the same between saves.
    """
    without_comments = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    start = re.search(r"\bpackage\s+Main\s*\{", without_comments)
    if start is None:
        return " ".join(without_comments.split())
    depth, end = 0, len(without_comments)
    for index in range(start.end() - 1, len(without_comments)):
        if without_comments[index] == "{":
            depth += 1
        elif without_comments[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    return " ".join((without_comments[:start.start()] + without_comments[end:]).split())


# --- Comparing saves -------------------------------------------------------

def initial_changes(state: ModelState) -> list[Change]:
    """The changes that build the first accepted save from nothing."""
    changes: list[Change] = [PartAdded(name, part.part_def, dict(part.values)) for name, part in state.parts.items()]
    changes.append(AlgorithmChanged(None, state.algorithm))
    return changes


def compare(old: ModelState, new: ModelState) -> list[Change]:
    """The changes from `old` to `new`. Raises `ModelRejected` for edits the
    demo doesn't support.
    """
    reasons = []
    if new.definitions != old.definitions:
        reasons.append("part defs or state machines changed: only package Main can be edited during the demo")
    for role in ("household", "battery", "pv", "grid"):
        if getattr(new, role) != getattr(old, role):
            reasons.append(f"the {role} can't be renamed, replaced or removed "
                           f"({getattr(old, role)} -> {getattr(new, role)})")
    for name in old.parts.keys() & new.parts.keys():
        if old.parts[name].part_def != new.parts[name].part_def:
            reasons.append(f"{name}: part def changed ({old.parts[name].part_def} -> {new.parts[name].part_def})")
    if reasons:
        raise ModelRejected(reasons)

    changes: list[Change] = []
    changes += [PartRemoved(name) for name in old.parts if name not in new.parts]
    changes += [PartAdded(name, part.part_def, dict(part.values))
                for name, part in new.parts.items() if name not in old.parts]
    for name, part in new.parts.items():
        if name in old.parts:
            old_values = old.parts[name].values
            changes += [ValueChanged(name, attribute, old_values[attribute], value)
                        for attribute, value in part.values.items() if old_values[attribute] != value]
    if new.algorithm != old.algorithm:
        changes.append(AlgorithmChanged(old.algorithm, new.algorithm))
    return changes


# --- Watching the file -----------------------------------------------------

@dataclass(frozen=True)
class WatchResult:
    """The outcome of one save: the changes to apply (possibly none), or the
    reasons it was rejected.
    """
    changes: list = field(default_factory=list)
    rejected: list = field(default_factory=list)


class ModelWatcher:
    """Polls the model file and reports each save as a `WatchResult` on
    `results`. Reloading runs in the watcher's own thread; `reloading` is
    true meanwhile, for the visualization.
    """

    def __init__(self, path: str, poll_interval: float = POLL_INTERVAL_SECONDS):
        self.path = path
        self.poll_interval = poll_interval
        self.results: "queue.Queue[WatchResult]" = queue.Queue()
        self.reloading = False
        self.state: Optional[ModelState] = None
        self._text: Optional[str] = None
        self._mtime: Optional[float] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def load_initial(self) -> ModelState:
        """Reads the file once, synchronously. Raises `ModelRejected` if the
        starting model can't be used: the demo shouldn't start on it.
        """
        self._mtime = os.path.getmtime(self.path)
        self._text = self._read_text()
        self.state = read_model_text(self._text)
        return self.state

    def start(self) -> None:
        if self.state is None:
            raise RuntimeError("load_initial() must succeed before start()")
        self._thread = threading.Thread(target=self._run, name="ModelWatcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _read_text(self) -> str:
        with open(self.path, encoding="utf-8") as file:
            return file.read()

    def _run(self) -> None:
        while not self._stop.wait(self.poll_interval):
            mtime = os.path.getmtime(self.path)
            if mtime == self._mtime:
                continue
            self._mtime = mtime
            text = self._read_text()
            if text == self._text:  # saved without changes, e.g. PyCharm's automatic save
                continue
            self._text = text
            # `reloading` is cleared only once the result is on the queue, so
            # a clock paused on it can't run between the two.
            self.reloading = True
            try:
                self.results.put(self._check(text))
            finally:
                self.reloading = False

    def _check(self, text: str) -> WatchResult:
        try:
            new_state = read_model_text(text)
            changes = compare(self.state, new_state)
        except ModelRejected as rejection:
            return WatchResult(rejected=rejection.reasons)
        self.state = new_state
        return WatchResult(changes=changes)
