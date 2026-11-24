"""Copy test for the running interpreter + simulation: can the runtime state and the
Fischertechnik `Factory` be copied at a paused frame, so that copy and original go
on identically and independently? This is what the goal-directed search's `copy()`
must guarantee: version 1 of the search runs a copy ahead in a "dream world" while
the real system waits at the lockstep pause.

Plan, results and why each workaround is needed: lipvm-migration-search.md ("The copy
test", "Results"). Ported from lipvm-dt's `lipvm_copy_test.py`; Parts below refer to
that plan.

The careful copy needs two workarounds, applied only while copying (`_copyable`);
LipVM itself is not changed:
- share the metamodel (and the AST) instead of copying it;
- copy pyecore collections field by field (`EOrderedSet` otherwise comes back empty).
"""

import collections
import contextlib
import copy
import dataclasses
import random
import types
from enum import Enum

import pytest
from pyecore.ecore import EModelElement, EProxy
from pyecore.valuecontainer import ECollection, EDerivedCollection

from core.language import Scenario
from core.operation import Operation, lazy_loop, lazy_while
from core.vm import VirtualMachine
from languages.sysmlv2.simulation_models.facade_proxy import SimulationBridge, ThreadChannel
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.syntax import get_executable_state_usages, get_part_instantiations

from tools.load_xmi_with_syntax import load


XMI = "tests/complete-interesting-simulation.xmi"
SEED = 0
WARMUP_MAX_STEPS = 3000
COMPARE_STEPS = 1500  # M in the plan; long enough to include a random token colour (first at ~1380)
ALONE_STEPS = 100     # K in the plan


# --- Part 1: setup and one system step ---

def _build() -> tuple[VirtualMachine, Factory]:
    vm = VirtualMachine()
    vm.scenario = Scenario(program_definition=load(XMI).contents[0])
    vm.init()  # builds the registry and queues the startup parts' InstantiateCommands
    return vm, Factory()


def _system_step(vm: VirtualMachine, factory: Factory) -> list[tuple[str, str | None]]:
    """One state machine's reactive pass, then one frame of the simulation: a reduced,
    single-threaded copy of on_tick() in main_lipvm_dtsimulation.py. Returns the
    events the Factory emitted in this frame."""
    vm.step()
    channel = vm.state.channel
    while not channel.instantiate_queue.empty():
        command = channel.instantiate_queue.get_nowait()
        factory.instantiate_part(command.qualified_name, command.part_def_name, command.attrs)
    while not channel.action_queue.empty():
        command = channel.action_queue.get_nowait()
        factory.execute_action(command.qualified_name, command.action_name, command.args)
    factory.tick()
    events = factory.drain_events()
    for item_name, source in events:
        SimulationBridge.emit_event(channel, item_name, source)
    channel.latest_snapshot.publish(factory.build_snapshot())
    return events


def _usages(vm: VirtualMachine) -> list:
    return get_executable_state_usages(vm.state.sysml.lookup_table_executable_state_usages)


# --- What is compared: values only, never object identity ---

def _plain(value, depth: int = 0):
    """`value` as plain data, so two copies compare by value. `repr` doesn't work:
    FactoryCoordinate shows its address."""
    if depth > 8:
        return "<too deep>"
    if isinstance(value, Enum):
        return value.name
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {_plain(k, depth + 1): _plain(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v, depth + 1) for v in value]
    if dataclasses.is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name), depth + 1) for f in dataclasses.fields(value)}
    if hasattr(value, "__dict__"):
        return {k: _plain(v, depth + 1) for k, v in vars(value).items()}
    return repr(value)


def _observe(vm: VirtualMachine, factory: Factory, events=()) -> dict:
    return {
        "state machines": {
            u.qualified_name: {
                "current": u.current.qualified_name if u.current is not None else None,
                "mailbox": [e.event_type.qualified_name for e in u.pending],
            } for u in _usages(vm)},
        "parts": {
            p.qualified_name: _plain(p.observed_values)
            for p in get_part_instantiations(vm.state.sysml.lookup_table_part_instantiations)},
        "factory snapshot": _plain(factory.build_snapshot()),
        "factory events": _plain(list(events)),
    }


def _first_difference(a, b, path: str = "") -> str | None:
    if type(a) is not type(b):
        return f"{path}: {a!r} != {b!r}"
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b), key=str):
            if key not in a or key not in b:
                return f"{path}/{key}: only in {'copy' if key not in a else 'original'}"
            found = _first_difference(a[key], b[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}: {a!r} vs {b!r}"
        for i, (x, y) in enumerate(zip(a, b)):
            found = _first_difference(x, y, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


# --- Parts 2 and 3: warm up, then stop at the paused frame ---

def _warm_up(vm: VirtualMachine, factory: Factory) -> None:
    """Step until at least one machine has left its first state and at least one
    token exists, so mailboxes and observed values are not empty."""
    first_state: dict[str, str] = {}
    for _ in range(WARMUP_MAX_STEPS):
        _system_step(vm, factory)
        moved = False
        for u in _usages(vm):
            if u.current is None:
                continue
            first_state.setdefault(u.qualified_name, u.current.qualified_name)
            moved |= u.current.qualified_name != first_state[u.qualified_name]
        if moved and list(factory.tokens):
            return
    raise RuntimeError(f"No machine left its first state with a token present within {WARMUP_MAX_STEPS} steps.")


def _at_copy_point(vm: VirtualMachine) -> bool:
    """The VM is stopped right before the FIRST state machine's pass of a round."""
    operation = vm._operation
    return (operation is not None and operation.is_step
            and bool(operation.args) and operation.args[0] is _usages(vm)[0])


def _go_to_copy_point(vm: VirtualMachine, factory: Factory) -> None:
    for _ in range(10 * len(_usages(vm)) + 10):
        if _at_copy_point(vm):
            return  # from here on, the Factory isn't ticked until the copy is made (the paused frame)
        _system_step(vm, factory)
    raise RuntimeError("Never stopped before the first state machine's pass.")


# --- Part 5: careful copy ---

def _deepcopy_collection(self, memo):
    """Copy a pyecore collection by its fields (owner, feature, items, ...), without
    calling its constructor or its append."""
    cls = type(self)
    new = cls.__new__(cls)
    memo[id(self)] = new
    for key, value in vars(self).items():
        new.__dict__[key] = copy.deepcopy(value, memo)
    if isinstance(self, list):
        list.extend(new, [copy.deepcopy(item, memo) for item in list.__iter__(self)])
    return new


@contextlib.contextmanager
def _copyable():
    """While active, the registry can be deep-copied; every patch is undone afterwards.

    - Share the metamodel: pyecore objects point to it (EValue.feature, _isset), so
      without this a copy drags the whole SysML metamodel along.
    - Copy pyecore collections field by field: EOrderedSet inherits
      ordered_set.OrderedSet's pickle state, which calls `__init__(items)` while
      pyecore's takes `(owner, feature)`, so the copy comes back empty; EList (a list
      subclass) would re-add its items through `append`, firing notifications.
    """
    patched = {cls: vars(cls).get("__deepcopy__") for cls in (EModelElement, ECollection, EDerivedCollection)}
    EModelElement.__deepcopy__ = lambda self, memo: self
    ECollection.__deepcopy__ = _deepcopy_collection
    EDerivedCollection.__deepcopy__ = _deepcopy_collection
    try:
        yield
    finally:
        for cls, previous in patched.items():
            if previous is None:
                del cls.__deepcopy__
            else:
                cls.__deepcopy__ = previous


def _ast_objects(vm: VirtualMachine) -> list:
    """Everything static during a run, shared by original and copy: the scenario,
    the AST and its resource."""
    root = vm.scenario.program_definition
    objects = [vm.scenario, root, *root.eAllContents()]
    resource = root.eResource
    if resource is not None:
        objects.append(resource)
        if getattr(resource, "resource_set", None) is not None:
            objects.append(resource.resource_set)
    return objects


def _careful_copy(vm: VirtualMachine, factory: Factory) -> tuple[VirtualMachine, Factory]:
    """A copy of the running VM and Factory; the original is not changed."""
    runtime, channel = vm.state, vm.state.channel

    # Share the AST (the metamodel is shared by _copyable()).
    memo = {id(obj): obj for obj in _ast_objects(vm)}

    # The channel's queues hold locks: substitute a new channel. Commands to the
    # simulation must already be drained at the paused frame; events for the next
    # round may be waiting and are carried over.
    for name in ("instantiate_queue", "action_queue", "model_update_queue",
                 "move_request_queue", "move_permission_queue"):
        assert getattr(channel, name).empty(), f"channel.{name} is not empty at the copy point"
    new_channel = ThreadChannel(name=channel.name)
    new_channel.lockstep_enabled = channel.lockstep_enabled
    new_channel.latest_snapshot.publish(copy.deepcopy(channel.latest_snapshot.read()))
    for command in copy.deepcopy(list(channel.event_queue.queue)):  # read without draining
        new_channel.event_queue.put(command)
    memo[id(channel)] = new_channel

    # runtime.pending_update_check is a VM method: point it at a new VM.
    new_vm = VirtualMachine()
    new_vm.scenario = vm.scenario
    memo[id(runtime.pending_update_check)] = new_vm.has_pending_update

    # ONE deepcopy call for the registry and the Factory.
    with _copyable():
        new_runtime, new_factory = copy.deepcopy((runtime, factory), memo)
    new_vm._runtime = new_runtime
    new_vm._pending_update = None

    # The copy's chain: this round's passes over the COPIED state machines, then the
    # round loop (as in Namespace.evaluate and read_events_and_execute, syntax.py).
    root = vm.scenario.program_definition
    new_usages = _usages(new_vm)
    chain = new_usages[0].evaluate(new_runtime)
    rest = lazy_loop(new_usages[1:], lambda element, runtime: element.evaluate(runtime), args=(new_runtime,))
    if rest is not None:
        chain.append(rest)
    chain.append(lazy_while(lambda runtime, stats: root.read_events_and_execute(runtime, stats),
                            Operation(lambda: True), args=(new_runtime, new_usages)))
    new_vm._operation = chain
    return new_vm, new_factory


# --- Part 7 helpers: what is reachable from where ---

_ATOMIC = (type(None), bool, int, float, complex, str, bytes, Enum, type,
           types.FunctionType, types.BuiltinFunctionType, types.ModuleType)


def _own_dict(obj) -> dict | None:
    """`obj.__dict__`, read without the object's own attribute lookup (which an
    EProxy overrides to load the SysML library); None if it has none."""
    try:
        state = object.__getattribute__(obj, "__dict__")
    except AttributeError:
        return None
    return state if isinstance(state, dict) else None


def _reachable(start, skip_ids: set[int]) -> dict[int, object]:
    """Every object reachable from `start`, except atomic values, metamodel elements,
    proxies and `skip_ids`. Function closures are not followed. Types are checked with
    `type(obj)` so an unresolved EProxy is never touched."""
    found: dict[int, object] = {}
    stack = [start]
    while stack:
        obj = stack.pop()
        kind = type(obj)
        if (issubclass(kind, _ATOMIC) or issubclass(kind, (EModelElement, EProxy))
                or id(obj) in skip_ids or id(obj) in found):
            continue
        found[id(obj)] = obj
        if issubclass(kind, dict):
            stack.extend(obj.keys())
            stack.extend(obj.values())
        elif issubclass(kind, (list, tuple, set, frozenset, collections.deque)):
            stack.extend(obj)
        if issubclass(kind, types.MethodType):
            stack.append(obj.__self__)
            continue
        state = _own_dict(obj)
        if state is not None:
            stack.extend(state.values())
        for slot in getattr(kind, "__slots__", ()):
            if isinstance(slot, str):
                try:
                    stack.append(object.__getattribute__(obj, slot))
                except AttributeError:
                    pass
    return found


# --- Fixture: original and copy at the paused frame ---

@pytest.fixture
def original_and_copy():
    """Yields (vm, factory, new_vm, new_factory): the original warmed up and stopped
    at the paused frame, and its careful copy. Seeds Python's random and restores the
    global random state afterwards, so other tests aren't affected."""
    saved = random.getstate()
    random.seed(SEED)
    try:
        vm, factory = _build()
        _warm_up(vm, factory)
        _go_to_copy_point(vm, factory)
        new_vm, new_factory = _careful_copy(vm, factory)
        yield vm, factory, new_vm, new_factory
    finally:
        random.setstate(saved)


# --- Tests ---

def test_naive_copy_fails():
    """Part 4: deep-copying the VM and Factory as a whole doesn't work, which is why
    the careful copy exists."""
    vm, factory = _build()
    _system_step(vm, factory)
    with pytest.raises(Exception):
        copy.deepcopy((vm, factory))


def test_copy_starts_at_the_copy_point(original_and_copy):
    """Part 5: the copy's VM is stopped right before its own first state machine's pass."""
    _, _, new_vm, _ = original_and_copy
    assert _at_copy_point(new_vm)


def test_copy_behaves_identically(original_and_copy):
    """Part 6: from the same random state, original and copy produce the same state
    machines, observed values, Factory snapshot and events at every step."""
    vm, factory, new_vm, new_factory = original_and_copy
    random_state = random.getstate()
    original_trace = [_observe(vm, factory, _system_step(vm, factory)) for _ in range(COMPARE_STEPS)]
    random.setstate(random_state)
    copy_trace = [_observe(new_vm, new_factory, _system_step(new_vm, new_factory)) for _ in range(COMPARE_STEPS)]

    for step, (a, b) in enumerate(zip(original_trace, copy_trace), start=1):
        difference = _first_difference(a, b)
        assert difference is None, f"original and copy differ at step {step}: {difference}"


def test_copy_shares_no_objects_with_the_original(original_and_copy):
    """Part 7, step 16: besides the AST and the metamodel, no mutable object is
    reachable from both. Immutable tuples are allowed: deepcopy shares them by design."""
    vm, factory, new_vm, new_factory = original_and_copy
    skip = {id(obj) for obj in _ast_objects(vm)}
    original = _reachable((vm.state, factory), skip)
    copied = _reachable((new_vm.state, new_factory), skip)
    shared = [obj for key, obj in copied.items() if key in original and not isinstance(obj, (tuple, frozenset))]
    assert not shared, collections.Counter(type(obj).__name__ for obj in shared)


def test_copy_observers_report_to_the_copy(original_and_copy):
    """Part 7, step 17: the copy's registry observers report to the copy's own
    synchronization manager. The shared AST is skipped: pyecore records every
    reference to an AST object in its `_inverse_rels`, so walking through the AST
    leads back into the original registry."""
    vm, _, new_vm, _ = original_and_copy
    manager = new_vm.state.synchronization_manager
    wrong = []
    for obj in _reachable(new_vm.state, {id(obj) for obj in _ast_objects(vm)}).values():
        state = _own_dict(obj)
        for listener in (state or {}).get("listeners") or []:
            target = getattr(listener, "_manager", None)
            if target is not None and target is not manager:
                wrong.append(type(listener).__name__)
    assert not wrong, wrong


def test_running_the_copy_leaves_the_original_unchanged(original_and_copy):
    """Part 7, step 18."""
    vm, factory, new_vm, new_factory = original_and_copy
    before = _observe(vm, factory)
    for _ in range(ALONE_STEPS):
        _system_step(new_vm, new_factory)
    assert _first_difference(before, _observe(vm, factory)) is None
