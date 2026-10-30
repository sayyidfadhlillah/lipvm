"""Entry point of the CleanWatts mock demo (see MOCK-DEMO.md, "The loop",
and DUMMY-DEMO.md for the story).

Run from the repository root:

    python -m languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.run_demo

Then click Start, and edit and save household.sysml while it runs.

Only wires the pieces together: the watcher reads the model once; a live
simulation and a "without changes" one are built from that read, each with
its own applier (and so its own battery controller); the visualization runs
the loop and pauses the clock while the watcher reloads; `on_tick` applies
the watcher's results to the live simulation only, then lets both
controllers decide.
"""
import argparse
import os
import queue
import sys
from dataclasses import dataclass
from typing import Callable

if __name__ == "__main__" and __package__ in (None, ""):
    # Also runnable as a plain script path, like tools/load_sysml.py.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir] * 5)))

from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.applier import Applier
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.simulation import MockEnergySimulation
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.visualization import EnergyVisualization
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.watcher import (
    ModelRejected, ModelWatcher, initial_changes,
)

DEFAULT_MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "household.sysml")
FRAMES_PER_SECOND = 60
SECONDS_PER_HOUR = 0.5


@dataclass
class Demo:
    watcher: ModelWatcher
    live: Applier
    baseline: Applier
    visualization: EnergyVisualization
    on_tick: Callable[[], None]


def build_demo(model_path: str, seconds_per_hour: float = SECONDS_PER_HOUR) -> Demo:
    """Reads the model once and wires everything; doesn't start the watcher
    thread or the window. Raises `ModelRejected` if the model can't be used.
    """
    watcher = ModelWatcher(model_path)
    state = watcher.load_initial()
    ticks_per_hour = max(1, round(seconds_per_hour * FRAMES_PER_SECOND))

    def new_applier() -> Applier:
        applier = Applier(MockEnergySimulation(ticks_per_hour), battery=state.battery,
                          house=state.household, grid=state.grid)
        applier.apply(initial_changes(state), record=False)
        return applier

    live, baseline = new_applier(), new_applier()
    visualization = EnergyVisualization(live, baseline, is_paused=lambda: watcher.reloading,
                                        title=os.path.basename(model_path))

    def on_tick() -> None:
        while True:
            try:
                result = watcher.results.get_nowait()
            except queue.Empty:
                break
            if result.rejected:
                visualization.post("rejected", result.rejected)
                print("Save rejected:", *result.rejected, sep="\n  ")
            elif result.changes:
                live.apply(result.changes)
                labels = [change.describe() for change in result.changes]
                visualization.post("applied", labels)
                print("Applied:", *labels, sep="\n  ")
            else:
                visualization.post("saved", ["no changes"])
                print("Saved, no changes")
        live.decide()
        baseline.decide()

    return Demo(watcher, live, baseline, visualization, on_tick)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sysml", nargs="?", default=DEFAULT_MODEL,
                        help="the .sysml model to run and watch (default: household.sysml next to this file)")
    parser.add_argument("--seconds-per-hour", type=float, default=SECONDS_PER_HOUR,
                        help=f"real seconds per simulated hour (default: {SECONDS_PER_HOUR})")
    args = parser.parse_args()

    try:
        demo = build_demo(args.sysml, args.seconds_per_hour)
    except ModelRejected as rejection:
        print(f"Can't start the demo, {args.sysml} can't be used:", *rejection.reasons, sep="\n  ")
        sys.exit(1)

    demo.watcher.start()
    try:
        demo.visualization.run(demo.live.simulation, on_tick=demo.on_tick, tick_rate=FRAMES_PER_SECOND)
    finally:
        demo.watcher.stop()


if __name__ == "__main__":
    main()
