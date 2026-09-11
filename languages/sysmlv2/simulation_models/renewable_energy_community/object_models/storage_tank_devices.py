import dataclasses

from citylearn.energy_model import StorageTank as CityLearnStorageTank

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class StorageTankSnapshot:
    """`current_soc`, not `soc` -- CityLearnStorageTank already has that
    name as a full time-series array property; reusing it here would shadow
    it (see StorageTank's own docstring below)."""

    current_soc: float


class StorageTank(CityLearnStorageTank, PartSimulationModel):
    """Extends `citylearn.energy_model.StorageTank` directly alongside
    `PartSimulationModel`, same pattern verified for `Building` in
    `citylearn_simulation_model.py` -- no wrapper, no custom `__init__`.
    Used here for `cooling_storage`; not itself instantiate_machine()'d
    (Milestone 1a bundles it into one Building call).
    """

    snapshot_type = StorageTankSnapshot

    def tick(self) -> None:
        pass

    @property
    def current_soc(self) -> float:
        return current_value(self.soc, self.time_step)
