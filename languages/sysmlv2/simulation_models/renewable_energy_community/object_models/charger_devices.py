import dataclasses
from typing import Optional

from citylearn.electric_vehicle_charger import Charger as CityLearnCharger

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class ChargerSnapshot:
    """`current_electricity_consumption`, not `electricity_consumption` --
    CityLearnCharger already has that name as a full time-series array
    property; reusing it here would shadow it (see Charger's own docstring
    below)."""

    current_electricity_consumption: float
    connected_electric_vehicle_name: Optional[str]


class Charger(CityLearnCharger, PartSimulationModel):
    """Extends `citylearn.electric_vehicle_charger.Charger` directly
    alongside `PartSimulationModel`, same pattern verified for `Building` in
    `citylearn_simulation_model.py` -- no wrapper, no custom `__init__`.
    Milestone 1b territory (`Cleanwatts-Sim-Issues.md` Issue 3) -- defined
    here for its snapshot capability, not yet accepted by
    instantiate_machine().
    """

    snapshot_type = ChargerSnapshot

    def tick(self) -> None:
        pass

    @property
    def current_electricity_consumption(self) -> float:
        return current_value(self.electricity_consumption, self.time_step - 1)

    @property
    def connected_electric_vehicle_name(self) -> Optional[str]:
        ev = self.connected_electric_vehicle
        return ev.name if ev is not None else None
