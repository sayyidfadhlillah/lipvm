import dataclasses

from citylearn.energy_model import PV as CityLearnPV

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class PVSnapshot:
    """`current_electricity_consumption`, not `electricity_consumption` --
    CityLearnPV already has that name as a full time-series array property;
    reusing it here would shadow it (see PV's own docstring below)."""

    current_electricity_consumption: float


class PV(CityLearnPV, PartSimulationModel):
    """Extends `citylearn.energy_model.PV` directly alongside
    `PartSimulationModel`, same pattern verified for `Building` in
    `citylearn_simulation_model.py` -- no wrapper, no custom `__init__`.
    Not itself instantiate_machine()'d (Milestone 1a bundles it into one
    Building call); exists so it gets `.snapshot()` for free once
    constructed as part of a Building's device_kwargs.
    """

    snapshot_type = PVSnapshot

    def tick(self) -> None:
        pass

    @property
    def current_electricity_consumption(self) -> float:
        return current_value(self.electricity_consumption, self.time_step - 1)
