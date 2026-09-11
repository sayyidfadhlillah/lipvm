import dataclasses

from citylearn.energy_model import ElectricHeater as CityLearnElectricHeater

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class ElectricHeaterSnapshot:
    """`current_electricity_consumption`, not `electricity_consumption` --
    CityLearnElectricHeater already has that name as a full time-series
    array property; reusing it here would shadow it (see ElectricHeater's
    own docstring below)."""

    current_electricity_consumption: float


class ElectricHeater(CityLearnElectricHeater, PartSimulationModel):
    """Extends `citylearn.energy_model.ElectricHeater` directly alongside
    `PartSimulationModel`, same pattern verified for `Building` in
    `citylearn_simulation_model.py` -- no wrapper, no custom `__init__`.
    Not yet accepted by instantiate_machine() (see
    `Cleanwatts-Sim-Issues.md`'s discussion on heating/cooling object_models);
    defined here for its snapshot capability regardless.
    """

    snapshot_type = ElectricHeaterSnapshot

    def tick(self) -> None:
        pass

    @property
    def current_electricity_consumption(self) -> float:
        return current_value(self.electricity_consumption, self.time_step - 1)
