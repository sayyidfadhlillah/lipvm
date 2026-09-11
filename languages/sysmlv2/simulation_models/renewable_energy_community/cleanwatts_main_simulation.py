"""CleanWatts demo driven through `CityLearnSimulation`
(`citylearn_simulation_model.py`) instead of hand-building a `Building`
directly -- a preview of exactly how the SysML interpreter will eventually
call this domain: `instantiate_machine()` once per building, then
`execute_action()`/`tick()` once per simulated hour, reading state back via
`get_machine()`/`build_snapshot()`. Nothing here talks to `CityLearnEnv`
directly any more; everything goes through `CityLearnSimulation`'s public
`BaseSimulationModel` surface, same as `factory_simulation_demo.py` does for
`Factory` in the fischertechnik domain.

Superseded by this rewrite: the original version of this file (which
predates `citylearn_simulation_model.py`) hand-built the `Building` and its
devices directly, including an EV charger (`electric_vehicle_chargers`) fed
by a toy one-EV-per-day schedule mirroring `cleanwatts-config.json`'s
R-H-01/EVC01 entity. That EV plumbing isn't carried over here: it's outside
Milestone 1a's device-bundling scope --
`CityLearnSimulation.instantiate_machine()` raises
`NotImplementedError`/`ValueError` if asked for `electric_vehicle_chargers`.
It'll come back once Milestone 1b (see `Cleanwatts-Sim-Issues.md`, Issue 3)
resolves the EV's non-containment ownership question and
`CityLearnSimulation` accepts it.

Environment
------------
Runs under this project's own `.venv` directly -- no separate Python 3.10
venv needed any more. Per `Architectural-Discussion.md` Topic 4: the
originally-documented `pandas==1.3.5` pin (which forced Python <=3.12,
incompatible with the interpreter's own >=3.14/3.11 floor) belonged to an
older CityLearn release; the currently pinned `citylearn==3.0.2` has no such
constraint, verified by actually running the interpreter's own test suite
under this venv (52 passed, 8 failed only on an unrelated missing `pygame`
dependency, since installed). On Windows, `import torch` still has to
happen before `pandas`/`citylearn` are imported below, or torch's native DLL
load fails (OSError: ... c10.dll or one of its dependencies) -- a
DLL-conflict ordering issue, not a version mismatch; setting
KMP_DUPLICATE_LIB_OK=TRUE also works around it if the import order alone
isn't enough.

Run as a module, not by path -- this file lives inside the package and uses
absolute imports (`languages.sysmlv2...`), which only resolve if the repo
root is on `sys.path`; running it by path instead puts this file's own
directory on `sys.path`, and the import fails with `ModuleNotFoundError: No
module named 'languages'`. From the repo root:

    python -m languages.sysmlv2.simulation_models.renewable_energy_community.cleanwatts_main_simulation
"""
import numpy as np
import torch  # noqa: F401 -- must import before citylearn/pandas, see module docstring

from languages.sysmlv2.simulation_models.renewable_energy_community.citylearn_simulation_model import (
    EPISODE_HOURS,
    CityLearnSimulation,
)

BUILDING_NAME = "SysMLBuilding1"


def live_weather_and_carbon_intensity(hour: int) -> tuple[float, float]:
    """Stand-in for the 'game' that would decide these values in real time --
    a scripted day/night temperature swing and a carbon-intensity dip at
    midday (more solar/wind on the grid). Purely to exercise the
    mutate-the-array-before-tick() mechanism, not real physics -- this is
    exactly where a live control panel or scripted scenario would plug in
    instead.
    """
    temperature = 15.0 + 8.0 * -np.cos(2 * np.pi * hour / 24)  # coolest ~3am, warmest ~3pm
    carbon_intensity = 0.35 - 0.15 * np.sin(np.pi * hour / 24)  # lower in daytime
    return float(temperature), float(max(carbon_intensity, 0.05))


def battery_policy(carbon_intensity: float) -> float:
    """Toy control rule closing the loop end to end: charge the battery when
    the grid is clean, discharge when it's dirty. This is the seam a SysML
    action/guard would eventually occupy -- a `do` action inside a
    'Charging'/'Discharging' state, once Cleanwatts-Sim-Issues.md Issue 2's
    `do`-action design is implemented, calling execute_action() the same way
    this function's result does below.
    """
    return 0.5 if carbon_intensity < 0.3 else -0.5


def main() -> None:
    sim = CityLearnSimulation()

    # instantiate_machine() -- exactly what the interpreter will call once
    # per `part` declaration in the SysML model, with `attrs` built from
    # that part's AttributeUsage values. Milestone 1a bundles every device
    # into this one call (Cleanwatts-Sim-Issues.md Issue 1).
    sim.instantiate_machine(BUILDING_NAME, "Building", {
        "electrical_storage": ("Battery", {"capacity": 10.0, "nominal_power": 5.0}),
        "pv": ("PV", {"nominal_power": 7.5}),
        "cooling_storage": ("StorageTank", {"capacity": 20.0}),
    })
    building = sim.get_machine(BUILDING_NAME)

    print(f"device specs -- battery capacity: {building.electrical_storage.capacity} kWh, "
          f"pv: {building.pv.nominal_power} kW, cooling storage: {building.cooling_storage.capacity} kWh")

    header = f"{'t':>3} {'temp(C)':>8} {'carbon':>7} {'batt_action':>11} {'batt_soc':>9} {'reward':>8}"
    header_printed = False

    for hour in range(EPISODE_HOURS):
        temperature, carbon_intensity = live_weather_and_carbon_intensity(hour)
        # Live-fed exogenous data: write this tick's real value into the
        # array cell tick() is about to read, instead of it having been
        # pre-loaded from a CSV before the episode started. Still reaches
        # straight into the real CityLearn Building object returned by
        # get_machine() -- CityLearnSimulation deliberately doesn't wrap or
        # proxy this (Cleanwatts-Sim-Issues.md: 'don't introduce additional
        # attributes unless necessary').
        building.weather._outdoor_dry_bulb_temperature[hour] = temperature
        building.carbon_intensity._carbon_intensity[hour] = carbon_intensity

        # execute_action() -- stages a value, doesn't apply it immediately
        # (Cleanwatts-Sim-Issues.md Issue 2). tick() is what actually calls
        # env.step() once, for every building/device at once.
        battery_action = battery_policy(carbon_intensity)
        sim.execute_action(BUILDING_NAME, "electrical_storage", {"value": battery_action})
        sim.tick()

        if not header_printed:
            # sim.env only exists from the first tick() onward (lazy
            # construction, Cleanwatts-Sim-Issues.md Issue 1) -- this is the
            # earliest point action_names can be read.
            print(f"active actions: {sim.env.action_names[0]}\n")
            print(header)
            header_printed = True

        soc = building.electrical_storage.current_soc
        reward = sim.last_reward[0]

        print(f"{hour:>3} {temperature:>8.2f} {carbon_intensity:>7.3f} "
              f"{battery_action:>11.2f} {soc:>9.3f} {reward:>8.3f}")

        if sim.last_terminated or sim.last_truncated:
            break


if __name__ == "__main__":
    main()
