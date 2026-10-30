"""The battery algorithms of household.sysml (`SelfConsumption`,
`PeakShaving`, `PriceArbitrage`) in Python, for the first, pure-Python
version of the CleanWatts mock demo (see MOCK-DEMO.md, "Controllers").

Each controller mirrors its SysML state machine one to one: the same states
with the same entry actions, the same `accept when` transitions in the same
order with the same guards. So that the LipVM interpreter can later replace
them without changes elsewhere, a controller

- reads only the snapshot (as the interpreter's guards do, through
  `SimulationBridge.read_attribute_from_snapshot`), and
- acts only through `execute_action` (as entry actions do), and only when it
  enters a state (an entry action runs once on entering its state), so being
  asked to decide every frame is harmless.

Like the state machines, it takes at most one transition per `decide` call.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from languages.sysmlv2.simulation_models.generic import BaseSimulationModel

# A guard reads the snapshots of the three parts bound to the state
# machine's parameters: battery, house, grid.
Guard = Callable[[object, object, object], bool]


@dataclass(frozen=True)
class Transition:
    """`accept when <guard> then <target>;` leaving `source`."""
    source: str
    guard: Guard
    target: str


class BatteryController:
    """Runs one battery algorithm: `entry; then <initial>;`, states with an
    entry action on the battery, and guarded transitions between them.

    `battery`, `house` and `grid` are the qualified names of the parts bound
    to the state machine's parameters (e.g. `Main::house1::battery1`).
    """

    initial: str = "Idle"
    # state name -> the battery action its entry runs
    entry_actions: dict[str, str] = {}
    # in declaration order; the first enabled one leaving the current state is taken
    transitions: tuple[Transition, ...] = ()

    def __init__(self, battery: str, house: str, grid: str):
        self.battery = battery
        self.house = house
        self.grid = grid
        self.state: Optional[str] = None  # None until the first decide()

    @property
    def algorithm(self) -> str:
        """The SysML state def this controller mirrors."""
        return type(self).__name__

    def decide(self, snapshot: dict, model: BaseSimulationModel) -> None:
        """Takes at most one step: enters the initial state on the first
        call, otherwise the first transition from the current state whose
        guard holds. Raises `KeyError` if a bound part isn't in `snapshot`.
        """
        if self.state is None:
            self._enter(self.initial, model)
            return

        battery, house, grid = snapshot[self.battery], snapshot[self.house], snapshot[self.grid]
        for transition in self.transitions:
            if transition.source == self.state and transition.guard(battery, house, grid):
                self._enter(transition.target, model)
                return

    def _enter(self, state: str, model: BaseSimulationModel) -> None:
        self.state = state
        model.execute_action(self.battery, self.entry_actions[state], {})


# The guards below are the SysML guards, read with the same names; 0.95 is
# the literal the SysML guards use.

class SelfConsumption(BatteryController):
    """Store the solar surplus, use it whenever the house needs more than
    the PV produces.
    """

    entry_actions = {
        "Idle": "standby",
        "Charging": "chargeFromSolar",
        "Discharging": "discharge",
    }
    transitions = (
        Transition("Idle", lambda battery, house, grid: house.netLoad < 0.0 and battery.soc < 0.95,
                   "Charging"),
        Transition("Idle", lambda battery, house, grid: house.netLoad > 0.0 and battery.soc > battery.reserve,
                   "Discharging"),
        Transition("Charging", lambda battery, house, grid: house.netLoad >= 0.0 or battery.soc >= 0.95,
                   "Idle"),
        Transition("Discharging", lambda battery, house, grid: house.netLoad <= 0.0 or battery.soc <= battery.reserve,
                   "Idle"),
    )


class PeakShaving(BatteryController):
    """Store the solar surplus, but only use it to keep grid import below
    peakLimit.
    """

    entry_actions = {
        "Idle": "standby",
        "Charging": "chargeFromSolar",
        "Discharging": "shavePeak",
    }
    transitions = (
        Transition("Idle", lambda battery, house, grid: house.netLoad < 0.0 and battery.soc < 0.95,
                   "Charging"),
        Transition("Idle", lambda battery, house, grid:
                   house.netLoad > battery.peakLimit and battery.soc > battery.reserve,
                   "Discharging"),
        Transition("Charging", lambda battery, house, grid: house.netLoad >= 0.0 or battery.soc >= 0.95,
                   "Idle"),
        Transition("Discharging", lambda battery, house, grid:
                   house.netLoad <= battery.peakLimit or battery.soc <= battery.reserve,
                   "Idle"),
    )


class PriceArbitrage(BatteryController):
    """Buy from the grid when cheap, use the stored energy when expensive."""

    entry_actions = {
        "Idle": "standby",
        "Charging": "chargeFromGrid",
        "Discharging": "discharge",
    }
    transitions = (
        Transition("Idle", lambda battery, house, grid:
                   grid.price <= battery.chargePrice and battery.soc < 0.95,
                   "Charging"),
        Transition("Idle", lambda battery, house, grid:
                   grid.price >= battery.dischargePrice and battery.soc > battery.reserve,
                   "Discharging"),
        Transition("Charging", lambda battery, house, grid:
                   grid.price > battery.chargePrice or battery.soc >= 0.95,
                   "Idle"),
        Transition("Discharging", lambda battery, house, grid:
                   grid.price < battery.dischargePrice or battery.soc <= battery.reserve,
                   "Idle"),
    )


# SysML state def name -> controller class; `batteryControl`'s type in
# household.sysml picks one.
CONTROLLERS: dict[str, type[BatteryController]] = {
    klass.__name__: klass for klass in (SelfConsumption, PeakShaving, PriceArbitrage)
}
