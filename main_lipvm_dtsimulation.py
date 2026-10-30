"""Integrated interpreter + simulation visualization.

Loads a SysML v2 model and runs it against a real simulation model (e.g.
Fischertechnik's `Factory`), on two threads:

- Main thread: the selected domain's own `SimulationVisualization.run()`
  (pygame requires this).
- Background thread: the interpreter's reactive loop, re-evaluating every
  `ExecutableStateUsage` on a tick.

Nothing runs until `on_start` is called in the simulation visualization. This `on_start`
just releases the interpreter thread, which then does the model's eager part-instantiation pass itself
and starts stepping.

Add a new simulation domain by adding one entry to `SIMULATION_MODELS`
below -- nothing else in this file needs to change.
"""

import argparse
import queue
import threading
import time
from dataclasses import dataclass

from core.language import Scenario
from core.vm import ProgramUpdateOption, VirtualMachine
from languages.sysmlv2.updates import AtomicUpdate
from languages.sysmlv2.simulation_models.facade_proxy import SimulationBridge, ThreadChannel
from languages.sysmlv2.simulation_models.fischertechnik.factory import Factory
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import FischertechnikVisualization
from languages.sysmlv2.simulation_models.generic import BaseSimulationModel, SimulationVisualization
from tools.load_sysml import load

# A Dict describing what Simulation Model and Visualization is ready to be used as part of this CLI
REGISTERED_SIMULATION_MODELS: dict[str, tuple[type[BaseSimulationModel], type[SimulationVisualization]]] = {
    "fischertechnik": (Factory, FischertechnikVisualization),
}

def build_simulation(sysml_path: str, simulation_model_class: type[BaseSimulationModel]) -> tuple[VirtualMachine, BaseSimulationModel]:
    """Loads the SysML model (represented by `sysml_path), constructs a fresh instance of `BaseSimulationModel`,
    and a fresh LipVM virtual machine. Deliberately doesn't step the virtual machine, it waits until it is started
    through the Main thread (Simulation Visualization thread).

    sysml_path: Path to the SysML model to be loaded (format .sysml)
    simulation_model_class: the actual simulation model class to be used
    """
    resource = load(sysml_path, keep_xmi=False)
    scenario = Scenario(program_definition=resource.contents[0])

    vm = VirtualMachine()
    vm.scenario = scenario
    vm.init()

    model = simulation_model_class()

    return vm, model

@dataclass(frozen=True)
class SubmittedUpdate:
    """An update file's updates on their way to the interpreter thread
    (window -> interpreter, `update_queue`): `name` is the file's name, for
    messages; `update` its `UPDATES` as one AtomicUpdate (see
    languages/sysmlv2/update_inbox.py)."""
    name: str
    update: AtomicUpdate

@dataclass(frozen=True)
class UpdateStatus:
    """What became of a SubmittedUpdate (interpreter -> window,
    `update_results`): `kind` is "submitted" (now pending in the VM, waiting
    for tranquility) or "rejected" (it can't be applied, never reached the
    VM); `message` says more."""
    kind: str
    name: str
    message: str

def _hand_over_update(vm: VirtualMachine, update_queue: queue.Queue, update_results: queue.Queue) -> None:
    """Between two `vm.step()` calls, on the interpreter thread: if no update
    is pending (the VM holds one at a time), takes the next queued one,
    checks it against the running model and submits it.

    Checked here, before `vm.submit`, because the registry belongs to this
    thread, and because an update that fails inside `apply()` would raise out
    of `vm.step()`, ending this thread and staying pending. Only the errors a
    wrong update file produces are caught (`LookupError`: unknown part or
    attribute; `ValueError`: a part def as owner); anything else is a bug and
    is raised.
    """
    if vm.has_pending_update():
        return
    try:
        item = update_queue.get_nowait()
    except queue.Empty:
        return

    try:
        item.update.check(vm.state)
        item.update.affected_elements(vm.state)
    except (LookupError, ValueError) as error:
        status = UpdateStatus("rejected", item.name, str(error))
    else:
        vm.submit(item.update, ProgramUpdateOption.HOTSWAP)
        status = UpdateStatus("submitted", item.name,
                              f"{len(item.update.updates)} update(s) pending, waiting for tranquility")
    print(f"Update {item.name} {status.kind}: {status.message}")
    update_results.put(status)

def run_interpreter_loop(vm: VirtualMachine, stop_event: threading.Event,
                          started_event: threading.Event, tick_delay: float,
                          update_queue: queue.Queue, update_results: queue.Queue) -> None:
    """
    The actual behaviour of the interpreter loop, which will live in the Background thread.
    Waits for `started_event` (set when the simulation visualization execute `on_start` method described in
    the `main` method), then does the model's one-time eager part-instantiation pass and repeatedly
    steps the VM until `stop_event` is set. Before each step, hands a queued update over to the VM
    (`_hand_over_update`).

    vm: LipVM virtual machine which will interpret the SysML model
    model: the actual simulation model class to be used
    stop_event: signals the loop to stop once set (e.g. when the visualization window closes)
    started_event: signals the interpreter thread to start, which is performed by the Main thread
    tick_delay: seconds to sleep between reactive passes
    update_queue: SubmittedUpdates from the window, to hand over to the VM
    update_results: where each one's UpdateStatus is reported back to the window
    """

    started_event.wait()
    if stop_event.is_set():
        return

    # vm.init() already enqueued an InstantiateCommand per Part described in
    # the SysML model (Namespace.evaluate() -> PartInstantiation.evaluate() ->
    # SimulationBridge.instantiate(), fire-and-forget); this first step starts
    # the first round. on_tick(), on the pygame thread, is what actually drains
    # these into `model` and prints each one as it happens -- this thread has no
    # way to know when that drain is done without adding new synchronization.
    vm.step()

    # Continue to execute LipVM virtual machine step until the stop signal is performed in the main thread
    while not stop_event.is_set():
        time.sleep(tick_delay)
        _hand_over_update(vm, update_queue, update_results)
        vm.step()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sysml", help=f"Path to the .sysml model to run")
    parser.add_argument("--tick-delay", type=float, default=0.02,
                         help="Seconds between interpreter reactive passes (default: 0.02)")
    parser.add_argument("--simulation-model", choices=sorted(REGISTERED_SIMULATION_MODELS),
                        help="Which simulation domain to run", required=True)
    args = parser.parse_args()

    model_class, visualization_class = REGISTERED_SIMULATION_MODELS[args.simulation_model]
    vm, model = build_simulation(args.sysml, model_class)

    stop_event = threading.Event()
    started_event = threading.Event()
    # Live updates: SubmittedUpdates from the window to the interpreter
    # thread, and their UpdateStatus back.
    update_queue: queue.Queue[SubmittedUpdate] = queue.Queue()
    update_results: queue.Queue[UpdateStatus] = queue.Queue()

    def on_start() -> None:
        """Start button's click handler. Just releases the interpreter
        thread -- must not block, since it runs inside the visualization's
        own event loop.
        """
        started_event.set()

    def on_tick() -> None:
        """Runs once per frame, after the model's own tick. Drains any
        queued instantiate/action commands and applies them (instantiate
        first, so a part created this call already exists for the
        action-drain and snapshot-publish steps that follow), then
        publishes a fresh snapshot for the interpreter thread to read.

        `Namespace.evaluate()` (syntax.py) enqueues one InstantiateCommand
        per PartInstantiation, once, during `vm.init()`; live
        changes to a part's configured values arrive separately, on
        `model_update_queue`. `model.instantiate_machine()` stays a no-op
        for a qualified_name it already has.
        """

        channel: ThreadChannel = vm.state.channel

        while not channel.instantiate_queue.empty():
            command = channel.instantiate_queue.get_nowait()
            model.instantiate_machine(command.qualified_name, command.part_def_name, command.attrs)

        while not channel.action_queue.empty():
            command = channel.action_queue.get_nowait()
            model.execute_action(command.qualified_name, command.action_name, command.args)

        for item_name, source_qualified_name in model.drain_events():
            SimulationBridge.emit_event(channel, item_name, source_qualified_name)

        channel.latest_snapshot.publish(model.build_snapshot())

    interpreter_thread = threading.Thread(
        target=run_interpreter_loop,
        args=(vm, stop_event, started_event, args.tick_delay, update_queue, update_results),
        daemon=True,
    )
    interpreter_thread.start()

    try:
        visualization_class().run(model, on_start, on_tick)  # blocks on the main thread until the window closes
    finally:
        stop_event.set()
        started_event.set()  # release the interpreter thread if it's still waiting on "Start"
        interpreter_thread.join(timeout=2)


if __name__ == "__main__":
    main()
