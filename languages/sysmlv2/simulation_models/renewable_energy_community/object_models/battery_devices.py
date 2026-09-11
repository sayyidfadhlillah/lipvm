import dataclasses

from citylearn.energy_model import Battery as CityLearnBattery

from languages.sysmlv2.simulation_models.generic import PartSimulationModel
from languages.sysmlv2.simulation_models.renewable_energy_community.object_models.time_series import current_value


@dataclasses.dataclass(frozen=True)
class BatterySnapshot:
    """Field names deliberately not `soc`/`electricity_consumption` --
    CityLearnBattery already has same-named properties returning the full
    time-series array; reusing those names here would shadow them (see
    Battery's own docstring below)."""

    current_soc: float
    current_electricity_consumption: float


class Battery(CityLearnBattery, PartSimulationModel):
    """Extends `citylearn.energy_model.Battery` directly alongside
    `PartSimulationModel`, same pattern verified for `Building` in
    `citylearn_simulation_model.py` -- no wrapper, no custom `__init__`.
    Not itself instantiate_machine()'d (Milestone 1a bundles it into one
    Building call); exists so it gets `.snapshot()` for free once
    constructed as part of a Building's device_kwargs.
    """

    snapshot_type = BatterySnapshot

    def tick(self) -> None:
        pass

    @property
    def current_soc(self) -> float:
        return current_value(self.soc, self.time_step)

    @property
    def current_electricity_consumption(self) -> float:
        return current_value(self.electricity_consumption, self.time_step - 1)
