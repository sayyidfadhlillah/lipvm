import dataclasses

from citylearn.electric_vehicle import ElectricVehicle as CityLearnElectricVehicle

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class ElectricVehicleSnapshot:
    current_soc: float


class ElectricVehicle(CityLearnElectricVehicle, PartSimulationModel):
    """Extends `citylearn.electric_vehicle.ElectricVehicle` directly
    alongside `PartSimulationModel`, same pattern verified for `Building` in
    `citylearn_simulation_model.py` -- no wrapper, no custom `__init__`.
    `CityLearnElectricVehicle` already has its own `name` property (plain
    settable string, same shape as `Building.name`), so no conflict there
    either. Milestone 1b territory (`Cleanwatts-Sim-Issues.md` Issue 3) --
    defined here for its snapshot capability, not yet accepted by
    instantiate_machine().
    """

    snapshot_type = ElectricVehicleSnapshot

    def tick(self) -> None:
        pass

    @property
    def current_soc(self) -> float:
        return current_value(self.battery.soc, self.time_step)
