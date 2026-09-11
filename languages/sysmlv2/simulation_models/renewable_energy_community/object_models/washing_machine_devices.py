import dataclasses

from citylearn.energy_model import WashingMachine as CityLearnWashingMachine

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class WashingMachineSnapshot:
    """`current_electricity_consumption`, not `electricity_consumption` --
    CityLearnWashingMachine already has that name as a full time-series
    array property; reusing it here would shadow it (see WashingMachine's
    own docstring below)."""

    current_electricity_consumption: float


class WashingMachine(CityLearnWashingMachine, PartSimulationModel):
    """Extends `citylearn.energy_model.WashingMachine` directly alongside
    `PartSimulationModel`, same pattern verified for `Building` in
    `citylearn_simulation_model.py` -- no wrapper, no custom `__init__`.
    `CityLearnWashingMachine` already has its own `name` property (plain
    settable string, same shape as `Building.name`), so no conflict there
    either. Not yet accepted by instantiate_machine(); defined here for its
    snapshot capability regardless.
    """

    snapshot_type = WashingMachineSnapshot

    def tick(self) -> None:
        pass

    @property
    def current_electricity_consumption(self) -> float:
        return current_value(self.electricity_consumption, self.time_step - 1)
