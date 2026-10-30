"""Mock energy simulation for the CleanWatts mock demo (see MOCK-DEMO.md,
"Simulation", and DUMMY-DEMO.md for the numbers it should reproduce).

One household with PV, a battery and appliances, simulated hour by hour from
fixed 24-hour input arrays. The SysML model (household.sysml) holds the
parameters; this module turns them into hourly data. No dataset is read and
nothing here imports CityLearn.

Implements `BaseSimulationModel`, the interface a LipVM driver talks to, so
the interpreter can drive it later without changes here: parts are created
with `instantiate_machine`, the battery is controlled with `execute_action`
(action names as in the SysML model), and `build_snapshot` returns
`{qualified_name: frozen snapshot}` with attributes named as in the SysML
model, as `SimulationBridge.read_attribute_from_snapshot` expects. Two
mock-only additions: `set_attribute` and `remove_machine`.

Part classes are named `Mock<PartDef>` and looked up through `PART_CLASSES`,
not `scan_for_subclasses`: that registry is global over the whole
simulation_models package and keyed by class name, and the CityLearn object
models already define `Battery`, `PV`, `HeatPump`, ...
"""
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

from languages.sysmlv2.simulation_models.generic import BaseSimulationModel, PartSimulationModel
from languages.sysmlv2.simulation_models.step_pacer import StepPacer

# One simulated hour every this many tick() calls: 0.5 s at the
# visualization's 60 frames per second, one simulated day every 12 s.
TICKS_PER_HOUR = 30

# How many simulated hours of history to keep for the visualization.
HISTORY_HOURS = 24 * 7

# Fixed 24-hour inputs, indexed by hour of day. Values from DUMMY-DEMO.md
# ("Numbers behind the expectations"); the story's starting values in
# household.sysml were tuned against them.
LOAD_SHAPE = [0.6, 0.5, 0.5, 0.5, 0.5, 0.6, 0.9, 1.4, 1.3, 0.9, 0.8, 0.8,
              0.9, 0.8, 0.8, 0.9, 1.1, 1.4, 1.7, 1.8, 1.7, 1.4, 1.0, 0.8]
SUN = [max(0.0, math.sin(math.pi * (h - 6) / 14)) if 6 <= h <= 20 else 0.0 for h in range(24)]
T_OUT = [6 + 5 * math.sin(math.pi * (h - 9) / 12) if 9 <= h <= 21
         else 6 - math.sin(math.pi * ((h - 21) % 24) / 12) for h in range(24)]  # degrees C, 5-11, spring
PRICE = [0.09, 0.08, 0.07, 0.07, 0.07, 0.08, 0.12, 0.16, 0.15, 0.11, 0.08, 0.06,
         0.05, 0.05, 0.06, 0.08, 0.12, 0.18, 0.22, 0.24, 0.22, 0.18, 0.13, 0.10]  # EUR/kWh

# Heat pump electricity = max(0, setpoint - T_OUT) * HEAT_PUMP_K / cop.
HEAT_PUMP_K = 0.3

# Charge level the battery never charges above; the same 0.95 the state
# machines' guards use (`battery.soc < 0.95`).
SOC_MAX = 0.95

INITIAL_SOC = 0.5


def _in_window(hour_of_day: int, start_hour: float, duration_hours: float) -> bool:
    """True if `hour_of_day` falls in the window starting at `start_hour`,
    including windows that wrap past midnight (e.g. 22.0 for 4 hours).
    """
    return (hour_of_day - start_hour) % 24 < duration_hours


# --- Snapshots -------------------------------------------------------------
# One frozen dataclass per part def: its configured attributes, then what the
# simulation reports. Field names are the SysML attribute names.

@dataclass(frozen=True)
class MockHouseholdSnapshot:
    standbyLoad: float
    netLoad: float
    gridImport: float


@dataclass(frozen=True)
class MockPVSnapshot:
    pvPeak: float
    output: float


@dataclass(frozen=True)
class MockGridSnapshot:
    price: float


@dataclass(frozen=True)
class MockBatterySnapshot:
    capacity: float
    maxPower: float
    reserve: float
    peakLimit: float
    chargePrice: float
    dischargePrice: float
    soc: float
    mode: str  # last action executed; not in the SysML model, for the visualization


@dataclass(frozen=True)
class MockApplianceSnapshot:
    power: float
    startHour: float
    durationHours: float
    load: float


@dataclass(frozen=True)
class MockHeatPumpSnapshot:
    setpoint: float
    cop: float
    load: float


@dataclass(frozen=True)
class MockChargerSnapshot:
    chargerPower: float
    chargeStartHour: float
    durationHours: float
    load: float


@dataclass(frozen=True)
class HourRecord:
    """One simulated hour, for the visualization's history."""
    hour: int                # hours since the start of the simulation
    load: float              # kW, standby + all devices
    device_loads: dict       # device qualified name -> kW
    pv: float                # kW
    net_load: float          # kW, load - pv
    battery_power: float     # kW, positive = charging, negative = discharging
    grid_import: float       # kW, negative = export
    soc: float               # battery charge level after this hour
    price: float             # EUR/kWh
    battery_mode: str


# --- Parts -----------------------------------------------------------------

class MockPart(PartSimulationModel):
    """Base for every mock part: knows its simulation (for the hour of day
    and the household's figures) and which of its attributes are configured
    in the SysML model, i.e. settable by `instantiate_machine` and
    `set_attribute`.
    """

    configured: Tuple[str, ...] = ()

    def __init__(self, simulation: "MockEnergySimulation"):
        super().__init__()
        self._simulation = simulation

    def configure(self, attrs: dict, require_all: bool) -> None:
        """Sets configured attributes from `attrs` (attribute name -> number).
        Raises on an attribute the part doesn't have as configured, and, if
        `require_all`, on a configured attribute missing from `attrs`.
        """
        unknown = set(attrs) - set(self.configured)
        if unknown:
            raise ValueError(f"{self.name}: not configured attributes of {type(self).__name__}: {sorted(unknown)}")
        if require_all:
            missing = set(self.configured) - set(attrs)
            if missing:
                raise ValueError(f"{self.name}: missing configured attributes: {sorted(missing)}")
        for attr_name, value in attrs.items():
            setattr(self, attr_name, float(value))

    def tick(self) -> None:
        """Most parts have nothing of their own to advance; the simulation
        computes the household's figures in `MockEnergySimulation._advance_hour`.
        """
        pass


class MockDevice(MockPart):
    """An appliance owned by the household, contributing `load` (kW) each
    hour. Devices can be added and removed while the simulation runs.
    """

    def __init__(self, simulation: "MockEnergySimulation"):
        super().__init__(simulation)
        self.load = 0.0

    def tick(self) -> None:
        self.load = self.load_at(self._simulation.hour_of_day)

    def load_at(self, hour_of_day: int) -> float:
        raise NotImplementedError("Sub-class must implement this method.")


class MockHousehold(MockPart):
    configured = ("standbyLoad",)
    snapshot_type = MockHouseholdSnapshot

    def __init__(self, simulation):
        super().__init__(simulation)
        self.netLoad = 0.0
        self.gridImport = 0.0


class MockPV(MockPart):
    configured = ("pvPeak",)
    snapshot_type = MockPVSnapshot

    def __init__(self, simulation):
        super().__init__(simulation)
        self.output = 0.0

    def tick(self) -> None:
        self.output = self.pvPeak * SUN[self._simulation.hour_of_day]


class MockGrid(MockPart):
    snapshot_type = MockGridSnapshot

    def __init__(self, simulation):
        super().__init__(simulation)
        self.price = 0.0

    def tick(self) -> None:
        self.price = PRICE[self._simulation.hour_of_day]


class MockBattery(MockPart):
    """Applies the mode set by its last action every hour until the next
    action, as an entry action's effect lasts while its state is active
    (`do` isn't implemented in LipVM). Action method names match the SysML
    `perform action` names, so `execute_action` can call them by name.
    """

    configured = ("capacity", "maxPower", "reserve", "peakLimit", "chargePrice", "dischargePrice")
    snapshot_type = MockBatterySnapshot

    def __init__(self, simulation):
        super().__init__(simulation)
        self.soc = INITIAL_SOC
        self.mode = "standby"

    def standby(self) -> None:
        self.mode = "standby"

    def chargeFromSolar(self) -> None:
        self.mode = "chargeFromSolar"

    def chargeFromGrid(self) -> None:
        self.mode = "chargeFromGrid"

    def discharge(self) -> None:
        self.mode = "discharge"

    def shavePeak(self) -> None:
        self.mode = "shavePeak"

    def power_for(self, net_load: float) -> float:
        """kW for this hour given the household's `net_load` (load - PV),
        positive = charging, negative = discharging, within `maxPower`,
        `SOC_MAX` and `reserve`. Doesn't change the charge level.
        """
        room = max(0.0, (SOC_MAX - self.soc) * self.capacity)
        available = max(0.0, (self.soc - self.reserve) * self.capacity)
        if self.mode == "standby":
            return 0.0
        if self.mode == "chargeFromSolar":
            return min(max(-net_load, 0.0), self.maxPower, room)
        if self.mode == "chargeFromGrid":
            return min(self.maxPower, room)
        if self.mode == "discharge":
            return -min(max(net_load, 0.0), self.maxPower, available)
        if self.mode == "shavePeak":
            return -min(max(net_load - self.peakLimit, 0.0), self.maxPower, available)
        raise ValueError(f"{self.name}: unknown battery mode {self.mode!r}")

    def apply(self, power: float) -> None:
        """Charges (positive) or discharges (negative) `power` kW for one hour."""
        self.soc += power / self.capacity


class MockWashingMachine(MockDevice):
    configured = ("power", "startHour", "durationHours")
    snapshot_type = MockApplianceSnapshot

    def load_at(self, hour_of_day: int) -> float:
        return self.power if _in_window(hour_of_day, self.startHour, self.durationHours) else 0.0


class MockDeferrableAppliance(MockWashingMachine):
    """Same fixed-cycle behaviour as the washing machine (e.g. a dishwasher)."""


class MockHeatPump(MockDevice):
    configured = ("setpoint", "cop")
    snapshot_type = MockHeatPumpSnapshot

    def load_at(self, hour_of_day: int) -> float:
        return max(0.0, self.setpoint - T_OUT[hour_of_day]) * HEAT_PUMP_K / self.cop


class MockCharger(MockDevice):
    configured = ("chargerPower", "chargeStartHour", "durationHours")
    snapshot_type = MockChargerSnapshot

    def load_at(self, hour_of_day: int) -> float:
        return self.chargerPower if _in_window(hour_of_day, self.chargeStartHour, self.durationHours) else 0.0


# SysML part def name -> mock class.
PART_CLASSES = {
    "Household": MockHousehold,
    "PV": MockPV,
    "Grid": MockGrid,
    "Battery": MockBattery,
    "WashingMachine": MockWashingMachine,
    "DeferrableAppliance": MockDeferrableAppliance,
    "HeatPump": MockHeatPump,
    "Charger": MockCharger,
}

# Part defs that must sit inside the household (household.sysml nests them
# in `house1`).
_OWNED_BY_HOUSEHOLD = (MockPV, MockBattery, MockDevice)


# --- Simulation ------------------------------------------------------------

class MockEnergySimulation(BaseSimulationModel):
    """One household (with its PV, battery and devices) and the grid,
    advanced one simulated hour every `TICKS_PER_HOUR` calls to `tick()`.

    Supports exactly one household, one PV, one battery and one grid; any
    number of devices. Ownership comes from the qualified name: a part named
    `Main::house1::washer1` belongs to the household `Main::house1`, which
    must already be instantiated.
    """

    def __init__(self, ticks_per_hour: int = TICKS_PER_HOUR):
        self._parts: dict[str, MockPart] = {}
        self._pacer = StepPacer(ticks_per_hour)
        self.hour = 0
        self.history: deque[HourRecord] = deque(maxlen=HISTORY_HOURS)
        # (load, device_loads, pv) of the hour begun but not yet ended.
        self._open_hour: Optional[tuple] = None

    # -- Lookups ------------------------------------------------------------

    @property
    def hour_of_day(self) -> int:
        return self.hour % 24

    def get_machine(self, qualified_name: str) -> Optional[MockPart]:
        return self._parts.get(qualified_name)

    def _single(self, klass: type) -> Optional[MockPart]:
        found = [part for part in self._parts.values() if type(part) is klass]
        return found[0] if found else None

    @property
    def household(self) -> Optional[MockHousehold]:
        return self._single(MockHousehold)

    @property
    def pv(self) -> Optional[MockPV]:
        return self._single(MockPV)

    @property
    def battery(self) -> Optional[MockBattery]:
        return self._single(MockBattery)

    @property
    def grid(self) -> Optional[MockGrid]:
        return self._single(MockGrid)

    @property
    def devices(self) -> list[MockDevice]:
        return [part for part in self._parts.values() if isinstance(part, MockDevice)]

    # -- BaseSimulationModel --------------------------------------------------

    def instantiate_machine(self, qualified_name: str, part_def_name: str, attrs: dict) -> None:
        """Creates and registers a part. Idempotent: a no-op if
        `qualified_name` is already registered.

        `attrs` maps each configured attribute name to a plain number (e.g.
        `{"capacity": 10.0}`), all configured attributes required. Unlike
        fischertechnik's composite `(custom_class_name, values)` pairs, this
        model only has scalars, in the shape TODOLIST-NOW.md plans for scalar
        configured values.
        """
        if qualified_name in self._parts:
            return

        klass = PART_CLASSES.get(part_def_name)
        if klass is None:
            raise ValueError(f"{qualified_name}: unknown part def {part_def_name!r}, expected one of {sorted(PART_CLASSES)}")

        single_kinds = (MockHousehold, MockPV, MockBattery, MockGrid)
        if klass in single_kinds and self._single(klass) is not None:
            raise ValueError(f"{qualified_name}: the mock supports only one {part_def_name}, "
                             f"already have {self._single(klass).name}")

        if issubclass(klass, _OWNED_BY_HOUSEHOLD):
            owner_name = qualified_name.rsplit("::", 1)[0]
            household = self.household
            if household is None or household.name != owner_name:
                raise ValueError(f"{qualified_name}: a {part_def_name} must be a part of the household "
                                 f"(instantiated first), but its owner is {owner_name!r}")

        part = klass(self)
        part.name = qualified_name
        part.configure(attrs, require_all=True)
        self._parts[qualified_name] = part

    def execute_action(self, qualified_name: str, action_name: str, args: dict) -> None:
        part = self._parts.get(qualified_name)
        if part is None:
            raise KeyError(f"{qualified_name}: no such part")
        getattr(part, action_name)(**args)

    def build_snapshot(self) -> dict:
        return {name: part.snapshot() for name, part in self._parts.items()}

    def drain_events(self) -> list[Tuple[str, Optional[str]]]:
        """The mock emits no events; the battery algorithms only use guards."""
        return []

    def tick(self) -> None:
        """Called every frame; every `TICKS_PER_HOUR` calls ends the current
        simulated hour and begins the next (see "One hour" below), otherwise
        does nothing.
        """
        if self._pacer.is_due("hour"):
            self._advance_hour()

    # -- Mock-only ------------------------------------------------------------

    def set_attribute(self, qualified_name: str, attrs: dict) -> None:
        """Changes configured attributes of an existing part (attribute name
        -> number); takes effect from the next simulated hour.
        """
        part = self._parts.get(qualified_name)
        if part is None:
            raise KeyError(f"{qualified_name}: no such part")
        part.configure(attrs, require_all=False)

    def remove_machine(self, qualified_name: str) -> None:
        """Removes a device. Only devices can be removed: the household, PV,
        battery and grid are needed for the simulation to run.
        """
        part = self._parts.get(qualified_name)
        if part is None:
            raise KeyError(f"{qualified_name}: no such part")
        if not isinstance(part, MockDevice):
            raise ValueError(f"{qualified_name}: only devices can be removed, not a {type(part).__name__}")
        del self._parts[qualified_name]

    # -- One hour -------------------------------------------------------------
    # Each simulated hour has two phases, so the battery reacts to the
    # current hour's consumption, not the previous one's:
    #   _begin_hour: devices, PV and price for hour h; netLoad is reported.
    #   (the controller, later LipVM, decides during the frames of hour h)
    #   _end_hour:   the battery is dispatched with that decision; grid
    #                import and the history record follow.
    # Device changes apply from the next _begin_hour, battery changes
    # (e.g. peakLimit) already at the coming _end_hour.

    def _advance_hour(self) -> None:
        """Ends the open hour (if any) and begins the next. Does nothing
        until the household, PV, battery and grid all exist.
        """
        if None in (self.household, self.pv, self.battery, self.grid):
            return
        if self._open_hour is not None:
            self._end_hour()
        self._begin_hour()

    def _begin_hour(self) -> None:
        h = self.hour_of_day
        for part in self._parts.values():
            part.tick()

        device_loads = {device.name: device.load for device in self.devices}
        load = self.household.standbyLoad * LOAD_SHAPE[h] + sum(device_loads.values())
        self.household.netLoad = load - self.pv.output
        self._open_hour = (load, device_loads, self.pv.output)

    def _end_hour(self) -> None:
        household, battery = self.household, self.battery
        load, device_loads, pv = self._open_hour
        net_load = household.netLoad

        battery_power = battery.power_for(net_load)
        battery.apply(battery_power)
        household.gridImport = net_load + battery_power

        self.history.append(HourRecord(
            hour=self.hour, load=load, device_loads=device_loads, pv=pv, net_load=net_load,
            battery_power=battery_power, grid_import=household.gridImport, soc=battery.soc,
            price=self.grid.price, battery_mode=battery.mode,
        ))
        self._open_hour = None
        self.hour += 1
