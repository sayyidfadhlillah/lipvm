"""Applies the watcher's change objects to the mock simulation and the
battery controller (see MOCK-DEMO.md, "Applying changes").

This is the piece LipVM replaces later: a value change becomes
`vm.submit(ChangeRuntimeAttributeValue(...))`, an algorithm change a swap of
the running state machine, adding or removing a device an update adding or
removing a `PartInstantiation`. Detection (watcher.py) stays as it is.
"""
from dataclasses import dataclass
from typing import Optional

from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.controllers import (
    CONTROLLERS, BatteryController,
)
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.simulation import (
    MockEnergySimulation,
)
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.watcher import (
    AlgorithmChanged, Change, PartAdded, PartRemoved, ValueChanged,
)


@dataclass(frozen=True)
class AppliedChanges:
    """One save's changes, applied at the start of simulated hour `hour`;
    drawn as a labelled line by the visualization.
    """
    hour: int
    changes: tuple

    def labels(self) -> list[str]:
        return [change.describe() for change in self.changes]


class Applier:
    """Owns the battery controller of one simulation and applies changes to
    both. `battery`, `house` and `grid` are the qualified names the
    controller is bound to; the watcher rejects saves that rename them.
    """

    def __init__(self, simulation: MockEnergySimulation, battery: str, house: str, grid: str):
        self.simulation = simulation
        self.battery = battery
        self.house = house
        self.grid = grid
        self.controller: Optional[BatteryController] = None
        self.applied: list[AppliedChanges] = []

    def apply(self, changes: list[Change], record: bool = True) -> None:
        """Applies `changes` in order. `record=False` for the initial build,
        which isn't a change the audience should see marked.
        """
        for change in changes:
            if isinstance(change, ValueChanged):
                self.simulation.set_attribute(change.part, {change.attribute: change.new})
            elif isinstance(change, PartAdded):
                self.simulation.instantiate_machine(change.part, change.part_def, dict(change.values))
            elif isinstance(change, PartRemoved):
                self.simulation.remove_machine(change.part)
            elif isinstance(change, AlgorithmChanged):
                self.controller = CONTROLLERS[change.new](battery=self.battery, house=self.house, grid=self.grid)
            else:
                raise TypeError(f"unknown change {change!r}")
        if record and changes:
            self.applied.append(AppliedChanges(self.simulation.hour, tuple(changes)))

    def decide(self) -> None:
        """Lets the controller decide on the simulation's current snapshot."""
        self.controller.decide(self.simulation.build_snapshot(), self.simulation)
