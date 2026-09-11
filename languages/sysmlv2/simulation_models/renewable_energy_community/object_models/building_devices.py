import dataclasses

from citylearn.building import Building as CityLearnBuilding

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class BuildingSnapshot:
    """Building-level only -- a building's own object_models each have their own
    snapshot (see the other files in this package), so this doesn't proxy
    any single device's state, just what's genuinely building-wide."""

    current_net_electricity_consumption: float


class Building(CityLearnBuilding, PartSimulationModel):
    """The SysML-registered part *is* the real CityLearn `Building` --
    verified this works before writing it this way (subclassing
    `citylearn.building.Building` directly alongside `PartSimulationModel`,
    no wrapper, no duplicated device references): CityLearn's own
    `Building.name` is already a plain settable string property, so
    `PartSimulationModel`'s contract needs nothing beyond what's already
    there, and `Building` doesn't define `tick()` itself, so no collision.
    Constructed with CityLearn's own full constructor signature (not
    Factory's generic `klass(self)` one-liner -- see
    `CityLearnSimulation.instantiate_machine()`), and behaves as a
    completely ordinary `CityLearnEnv` building once constructed --
    `env.buildings[i] is` this exact instance.

    Not a device the way the rest of this package's classes are -- it's the
    district-registered part -- but lives here alongside them regardless
    (per discussion), rather than in `citylearn_simulation_model.py`.
    """

    snapshot_type = BuildingSnapshot

    def tick(self) -> None:
        """No-op -- the real stepping happens once at the district level,
        in CityLearnSimulation.tick(), same as Architectural-Discussion.md
        Topic 1's 'Supporting classes needed' proposed."""
        pass

    @property
    def current_net_electricity_consumption(self) -> float:
        return current_value(self.net_electricity_consumption, self.time_step - 1)
