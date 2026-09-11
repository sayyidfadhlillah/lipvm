"""CityLearn-backed BaseSimulationModel -- same responsibility as
`fischertechnik/factory.py`'s `Factory`, for the CleanWatts/renewable-energy-
community domain. Generalizes `cleanwatts_main_simulation.py` (root, kept as
the standalone proof this is built from) into something an interpreter can
drive via `instantiate_machine`/`execute_action`/`tick`/`build_snapshot`/
`drain_events`.

Milestone 1a scope only (see `Cleanwatts-Sim-Issues.md`, Issue 1): building-
owned object_models (battery/PV/cooling storage), no EV/charger pairing yet --
that's Milestone 1b, deliberately deferred (Issue 3's ownership question
isn't answered here). All buildings must be instantiated before the first
`tick()`; hot-swapping a building in mid-run is Milestone 2, not implemented
here either.

Naming convention for this domain (per discussion): no `Machine` suffix
anywhere -- a registered/snapshot-capable part is named after the real
CityLearn class it extends (`Building`, `Battery`, `PV`, ...), and its
snapshot is `<Name>Snapshot` (`BuildingSnapshot`, `BatterySnapshot`, ...).

`Building` and every device (`Battery`, `PV`, `StorageTank`, `HeatPump`,
`ElectricHeater`, `WashingMachine`, `DeferrableAppliance`, `Escalator`,
`Charger`, `ElectricVehicle`) each live in their own file under `object_models/`
(one file per kind, e.g. `object_models/pv_devices.py` holds `PV`+`PVSnapshot` --
mirrors fischertechnik/fischertechnik_parts/'s one-file-per-machine-kind
convention, verified against `conveyor_belt.py` before adopting it here).
Each extends the real CityLearn class directly alongside
`PartSimulationModel`, no wrapper, no duplicated attributes. Only `Building`
is actually registered/instantiated via `instantiate_machine()` right now
(Milestone 1a's device-bundling decision, see below); the device classes
exist so every device gets its own `.snapshot()` for free once constructed
as part of a Building's device_kwargs, for use by a future
KPI/visualization layer or a SysML guard reading
`building.electrical_storage.snapshot()` directly -- not because they're
separately SysML-instantiated parts.

`Transport`: per Architectural-Discussion.md Topic 4, CityLearn no longer
needs a separate OS process (superseded Topic 3) -- this class is meant to
be driven the same way `Factory` is, over `ThreadChannel`, in-process.
"""
from typing import Optional, Tuple

import torch  # noqa: F401 -- must import before citylearn/pandas, see cleanwatts_main_simulation.py's module docstring (DLL load-order issue on Windows)

from citylearn.building import Building as CityLearnBuilding
from citylearn.citylearn import CityLearnEnv

from languages.sysmlv2.simulation_models.generic import BaseSimulationModel, PartSimulationModel
from languages.sysmlv2.simulation_models.registry import scan_for_subclasses
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.battery_devices import Battery
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.building_devices import Building
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.pv_devices import PV
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.storage_tank_devices import StorageTank

# Milestone 1b's object_models (heat_pump_devices/electric_heater_devices/
# washing_machine_devices/deferrable_appliance_devices/escalator_devices/
# charger_devices/electric_vehicle_devices) aren't imported here -- nothing
# in this file references them yet (not in _DEVICE_ATTRIBUTE_CLASSES below).
# scan_for_subclasses() still discovers them independently, by walking the
# package tree directly, not through this file's imports.

# Bundled CityLearn schema used purely as a scaffolding source (weather/
# pricing/episode-tracker/action-metadata arrays) for every Building this
# simulation constructs -- same borrowing pattern as
# cleanwatts_main_simulation.py's build_device_spec_building(), see
# Architectural-Discussion.md Topic 2 Part 1. Placeholder constants: these
# should eventually come from SysML model configuration, not be hardcoded
# here -- not addressed yet.
SCHEMA_NAME = "citylearn_challenge_2022_phase_1"
EPISODE_HOURS = 24


# attrs keys instantiate_machine() accepts for a Building part, and the
# device class each one must construct. Milestone 1a scope only --
# electric_vehicle_chargers/EV support is Milestone 1b (Cleanwatts-Sim-Issues.md
# Issue 3); requesting it raises rather than silently ignoring it. Points at
# object_models/'s classes (not the raw citylearn ones) so every
# Milestone-1a-constructed device gets snapshot capability for free.
_DEVICE_ATTRIBUTE_CLASSES = {
    "electrical_storage": Battery,
    "pv": PV,
    "cooling_storage": StorageTank,
}


class CityLearnSimulation(BaseSimulationModel):
    """Central registry + district-level driver for every Building in the
    simulation -- parallel to `Factory`, minus the token bookkeeping
    (fischertechnik-specific) and the per-machine `StepPacer` (fischertechnik-
    specific too, for smoothing rendered movement; CityLearn's hourly
    timestep has nothing analogous to pace, see Cleanwatts-Sim-Issues.md
    Issue 2's 'dissolved (1)').

    Deliberately holds almost no extra state beyond the live `CityLearnEnv`
    itself (per discussion: 'don't introduce additional attributes unless
    necessary') -- the building list is read via `self.env.buildings`, and
    each building's own object_models via that building's own properties, not
    mirrored into a separate registry.
    """

    def __init__(self):
        self.env: Optional[CityLearnEnv] = None
        # Buildings instantiated but not yet folded into a live env --
        # CityLearnEnv needs the *whole* building list at construction time
        # (see Cleanwatts-Sim-Issues.md Issue 1), so this is the minimum
        # unavoidable bookkeeping until the first tick() builds self.env.
        self._pending_buildings: list[Building] = []
        # {qualified_name: {action_name: value}} -- staged by execute_action,
        # read (not cleared) by tick(). Placeholder lifecycle: see
        # execute_action()'s docstring.
        self._staged_actions: dict[str, dict[str, float]] = {}
        self._template_building: Optional[CityLearnBuilding] = None
        # env.step()'s reward/terminated/truncated, captured by tick() -- not
        # part of BaseSimulationModel's tick() -> None contract, and not
        # per-building the way build_snapshot() is, so these live as plain
        # instance state instead, same as `env` itself.
        self.last_reward: Optional[list] = None
        self.last_terminated: bool = False
        self.last_truncated: bool = False

    def _borrow_template_scaffolding(self) -> CityLearnBuilding:
        """Lazily loads one bundled-schema building, once, purely to harvest
        weather/pricing/episode_tracker/observation_metadata/action_metadata
        for every Building this simulation constructs -- same borrowing
        pattern as cleanwatts_main_simulation.py's build_device_spec_building(),
        generalized to be called once per process rather than once per script
        run.
        """
        if self._template_building is None:
            template_env = CityLearnEnv(
                schema=SCHEMA_NAME, central_agent=True, buildings=[0], episode_time_steps=EPISODE_HOURS,
            )
            self._template_building = template_env.buildings[0]

        return self._template_building

    def get_machine(self, qualified_name: str) -> Optional[Building]:
        for building in self._pending_buildings:
            if building.name == qualified_name:
                return building

        if self.env is not None:
            for building in self.env.buildings:
                if building.name == qualified_name:
                    return building

        return None

    def instantiate_machine(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        """Constructs one whole Building from `attrs` in a single call --
        Milestone 1a's resolution of Issue 1's 'one call per building vs.
        one per device' question: one SysML part = one Building, all its
        object_models bundled into this one call, matching
        build_device_spec_building()'s proven shape exactly. Idempotent,
        same contract as Factory's version.
        """
        if self.get_machine(qualified_name) is not None:
            return

        klass = scan_for_subclasses(PartSimulationModel)[part_def_name]
        if not issubclass(klass, CityLearnBuilding):
            raise NotImplementedError(
                f"'{part_def_name}' is not a building part -- only building-owned object_models are "
                f"supported so far (Milestone 1a; see Cleanwatts-Sim-Issues.md Issue 3 for EV/charger support)."
            )

        device_kwargs = {}
        for attr_name, (custom_class_name, values) in attrs.items():
            expected_class = _DEVICE_ATTRIBUTE_CLASSES.get(attr_name)
            if expected_class is None:
                raise ValueError(
                    f"Unsupported device attribute '{attr_name}' on building '{qualified_name}' -- "
                    f"Milestone 1a only supports {sorted(_DEVICE_ATTRIBUTE_CLASSES)} "
                    f"(electric_vehicle_chargers/EV is Milestone 1b, see Cleanwatts-Sim-Issues.md Issue 3)."
                )

            if custom_class_name != expected_class.__name__:
                raise ValueError(
                    f"Attribute '{attr_name}' on building '{qualified_name}' declared class "
                    f"'{custom_class_name}', expected '{expected_class.__name__}'."
                )

            device_kwargs[attr_name] = expected_class(**values)

        template = self._borrow_template_scaffolding()
        building = klass(
            energy_simulation=template.energy_simulation,
            weather=template.weather,
            observation_metadata=template.observation_metadata,
            action_metadata=template.action_metadata,
            episode_tracker=template.episode_tracker,
            carbon_intensity=template.carbon_intensity,
            pricing=template.pricing,
            name=qualified_name,
            **device_kwargs,
        )
        self._pending_buildings.append(building)

    def execute_action(self, qualified_name: str, action_name: str, args: dict) -> None:
        """Stages a value for the next tick() to fold into the shared action
        vector -- doesn't call anything on the device directly (see
        Cleanwatts-Sim-Issues.md Issue 2: CityLearn only applies actions via
        one batched env.step() covering every building/device at once).

        Placeholder lifecycle, not yet the real design: a staged value
        persists until overwritten -- tick() does not clear it. This will
        need revisiting once `do` actions (Issue 2's agreed resolution for
        action persistence) are actually implemented in the interpreter;
        for now this just needs *a* well-defined behavior to be testable in
        isolation.

        `args` convention (placeholder, not yet settled on the interpreter
        side): a single `{"value": <float in [-1, 1]>}`.
        """
        if self.get_machine(qualified_name) is None:
            raise ValueError(f"'{qualified_name}' is not an instantiated part.")

        self._staged_actions.setdefault(qualified_name, {})[action_name] = args["value"]

    def tick(self) -> None:
        """Advances the whole simulation by one CityLearn timestep.

        First call constructs the live CityLearnEnv from every building
        instantiated so far (lazy construction -- Cleanwatts-Sim-Issues.md
        Issue 1, Milestone 1a) and resets it. Every call assembles one
        action vector from whatever's currently staged and calls
        env.step() once -- CityLearn has no finer-grained tick than that
        (see Issue 1's 'Ruled out' note on per-device next_time_step()); no
        per-machine pacing loop like Factory.tick()'s StepPacer, since
        nothing here needs independent pacing (Issue 2's 'dissolved (1)').

        Stores env.step()'s reward/terminated/truncated on
        self.last_reward/last_terminated/last_truncated -- can't return them
        (tick() -> None is fixed by BaseSimulationModel's contract), and
        they're not per-building the way build_snapshot() is, so they live
        as plain instance state instead, read separately after tick().
        """
        if self.env is None:
            if not self._pending_buildings:
                raise RuntimeError("tick() called with no buildings instantiated yet.")

            self.env = CityLearnEnv(
                schema=SCHEMA_NAME, central_agent=True, buildings=self._pending_buildings,
                episode_time_steps=EPISODE_HOURS,
            )
            self.env.reset()
            self._pending_buildings = []

        actions = []
        for building, action_names in zip(self.env.buildings, self.env.action_names):
            staged = self._staged_actions.get(building.name, {})
            actions.append([staged.get(name, 0.0) for name in action_names])

        _, self.last_reward, self.last_terminated, self.last_truncated, _ = self.env.step(actions)

    def build_snapshot(self) -> dict:
        buildings = self.env.buildings if self.env is not None else self._pending_buildings
        return {building.name: building.snapshot() for building in buildings}

    def drain_events(self) -> list[Tuple[str, Optional[str]]]:
        """CityLearn has no native event concept -- Architectural-Discussion.md
        Topic 1 proposed an empty list for the first cut; deriving events
        (comfort violation, cost threshold crossed) from observations is
        real design work, deferred rather than guessed at now.
        """
        return []
