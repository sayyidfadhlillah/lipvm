"""Generic (domain-agnostic) Facade+Proxy infrastructure for thread-confined
access to a simulation object owned by the simulation visualization thread.
"""

import queue
from dataclasses import dataclass

from core.language import RuntimeStateElement


class PartNotReadyError(Exception):
    """Raised when a part isn't in the published snapshot yet -- either no
    snapshot has been published, or this part specifically hasn't been
    instantiated yet. An ordinary startup race, not a real error -- its
    own exception type so a caller that wants to treat "not ready yet" as
    non-fatal (e.g. a transition guard) can catch exactly this.
    """


@dataclass(frozen=True)
class InstantiateCommand:
    """Fire-and-forget style command that is executed by the SysML interpreter when
    a part needs to be instantiated.

    qualified_name: the part's full SysML name
    part_def_name: which PartDef to construct
    attrs: attr_name -> (custom_class_name, values) pairs, one per
        CompositeCustomValue redefinition (e.g. "placementCoordinate" ->
        ("FactoryCoordinate", {"x": 10.0, "y": 0.0, "degrees": 0.0}))
    """
    qualified_name: str
    part_def_name: str
    attrs: dict


@dataclass(frozen=True)
class ActionCommand:
    """Fire-and-forget style command that is executed by the SysML interpreter when
    an needs to be performed, which will affect the simulation state.

    qualified_name: the target part's full SysML name
    action_name: which method to call on it
    args: keyword arguments for that call
    """
    qualified_name: str
    action_name: str
    args: dict


@dataclass(frozen=True)
class SetAttributeCommand:
    """Fire-and-forget command sent by the SysML interpreter after a live
    update changed configured attribute values of running parts: one batch
    per update, so the simulation applies every change in the same frame.

    parts: qualified_name -> {attr_name: (custom_class_name, values)}, the
        same per-part shape as InstantiateCommand.attrs, holding only the
        changed attributes (e.g. "Main::tokenDepo" -> {"placementCoordinate":
        ("FactoryCoordinate", {"x": 25.0, "y": 30.0, "degrees": 180.0})})
    """
    parts: dict


@dataclass(frozen=True)
class EventCommand:
    """Fire-and-forget command flowing the other way: an event the
    simulation side finished producing, to be delivered into the
    interpreter's ExecutableStateUsage mailboxes (see EVENT-QUEUE-DESIGN.md).

    item_name: the ItemDef's bare declared name (e.g.
        "VGRCommandSuccessEventMessage"), not a qualified one -- the
        simulation side has no access to the parsed SysML model to resolve
        one itself, so resolution to a qualified name happens later, on
        the interpreter thread (see LookupTable.get_reference_by_name()).
    source_qualified_name: the emitting part's qualified name (e.g.
        "Main::vgr1"), or None for a broadcast event with no specific origin
        (e.g. StopEventMessage).
    """
    item_name: str
    source_qualified_name: str | None = None


class SimulationSnapshot:
    """Single-value "topic" one thread publishes to and any number of
    others read from -- always holds just the latest value, no backlog (a
    `queue.Queue` would be the wrong tool: a stale snapshot is worthless
    once a newer one exists).

    `publish()` is a single reference assignment, atomic under CPython's
    GIL, so no lock is needed on either side. `read()` returns `None`
    before the first `publish()` call -- callers must handle that.
    """

    def __init__(self):
        self._value = None

    def publish(self, value) -> None:
        self._value = value

    def read(self):
        return self._value


class ThreadChannel(RuntimeStateElement):
    """Bundles everything the interpreter thread and the owning thread use
    to communicate: a published snapshot for reads, plus one-way queues
    for `instantiate`/`call_action` -- all 3 `SimulationBridge` operations,
    none of them blocking. The one exception is lockstep while an update is
    pending (design doc, Topic 10): the simulation asks on
    `move_request_queue` and waits for the answer on `move_permission_queue`,
    the only place where one thread waits for the other.

    A `RuntimeStateElement` so it can be registered directly on `runtime`
    and reached as `runtime.channel` -- `SimulationBridge` itself holds no
    state and is never instantiated, just a namespace of static methods
    that take this channel as an explicit argument.

    self.latest_snapshot: the latest SimulationSnapshot published by the Simulation Model and its visualization
    self.action_queue: a queue of actions to be executed by the Simulation model and its visualization
    self.instantiate_queue: a queue of parts to be instantiated in the Simulation model and its visualization
    self.model_update_queue: a queue of model changes from live updates (one item per update, e.g. a SetAttributeCommand batch) to be applied to running parts
    self.event_queue: a queue of events produced by the Simulation model, to be delivered to the interpreter
    self.move_request_queue: the simulation's "may I move past frame N?", a frame number, while an update is pending
    self.move_permission_queue: the interpreter's "go", the same frame number; both sides raise on a mismatch
    self.lockstep_enabled: whether a simulation takes part in the request and response; False (e.g. in tests)
        means nobody will ask, so the interpreter must not wait. Set by the driver before the interpreter thread starts
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.latest_snapshot = SimulationSnapshot()
        self.action_queue = queue.Queue()
        self.instantiate_queue = queue.Queue()
        self.model_update_queue = queue.Queue()
        self.event_queue = queue.Queue()

        # Live experience-related functionality
        self.move_request_queue = queue.Queue()
        self.move_permission_queue = queue.Queue()
        self.lockstep_enabled = False

class SimulationBridge:
    """Static utility surface for whatever simulation domain is plugged in
    underneath -- everything on the interpreter side goes through this
    instead of reaching into a domain's own simulation model directly.

    Never instantiated: every method takes the `ThreadChannel` it operates
    on as an explicit argument (reached as `runtime.channel`) rather than
    holding one as instance state. Domain-agnostic: only deals in
    `qualified_name` strings, plain dicts, and the generic command/channel
    types above -- nothing here knows about any specific domain's shape.

    No `get_snapshot()`/`channel` wrapper here -- a caller with a
    `ThreadChannel` just reads `channel.latest_snapshot.read()` directly.
    """

    @staticmethod
    def instantiate(channel: ThreadChannel, qualified_name: str, part_def_name: str, **attrs):
        """Enqueues an `InstantiateCommand` -- fire-and-forget. The owning
        thread drains and executes these once per tick.
        """
        channel.instantiate_queue.put(InstantiateCommand(qualified_name, part_def_name, attrs))

    @staticmethod
    def call_action(channel: ThreadChannel, qualified_name: str, action_name: str, **args):
        """Enqueues an `ActionCommand` -- fire-and-forget. The owning
        thread drains and executes these once per tick; it's the only
        thread that ever calls a method on a machine.
        """
        channel.action_queue.put(ActionCommand(qualified_name, action_name, args))

    @staticmethod
    def set_attributes(channel: ThreadChannel, parts: dict):
        """Enqueues one `SetAttributeCommand` for a whole batch of changed
        attribute values -- fire-and-forget. The owning thread drains and
        applies these once per tick, so every change in the batch lands in
        the same frame.
        """
        channel.model_update_queue.put(SetAttributeCommand(parts))

    @staticmethod
    def emit_event(channel: ThreadChannel, item_name: str, source_qualified_name: str | None = None):
        """Enqueues an `EventCommand` -- fire-and-forget, the reverse
        direction from `instantiate`/`call_action`. The owning thread
        (simulation side) calls this once per tick with whatever it
        collected via `Factory.drain_events()`; the interpreter thread
        drains `channel.event_queue` and delivers each one into every
        running `ExecutableStateUsage`'s `pending` mailbox (see
        EVENT-QUEUE-DESIGN.md).
        """
        channel.event_queue.put(EventCommand(item_name, source_qualified_name))


class SynchronizationManager(RuntimeStateElement):
    """Interpreter-side record of configured attribute values that live
    updates changed, sent to the simulation as one batch per `flush`
    (design doc, Language-Safe-and-Execution-Tranquility-points.md, Topic 10
    "Syncing a runtime change to the simulation").

    A `RuntimeStateElement` reached as `runtime.synchronization_manager`,
    registered next to the channel. Unlike `ThreadChannel`, it is used by the
    interpreter thread only: the simulation thread never touches it.

    The record is filled by language-specific observers, which convert each
    changed value before calling `record` (the same split as instantiation:
    the language converts, the bridge only enqueues). Updates always replace a
    configured value rather than change it in place, so a value converted when
    recorded is still the current one at `flush`.

    It also runs the interpreter's side of lockstep (design doc, Topic 10,
    "Lockstep while an update is pending") in `start_round`, and notes how
    the round's values were copied.

    self._record: qualified_name -> {attr_name: (custom_class_name, values)},
        the shape of `SetAttributeCommand.parts`; the last change to an
        attribute wins
    self.values_copied_while_paused: whether this round waited for the
        simulation's question before its values were copied, i.e. copied while
        the simulation was paused; always False with lockstep disabled. Read by
        `TranquilUpdate.condition()` when lockstep is enabled
    self._owed_answer: the frame number of the question this round took,
        answered with "go" at the start of the next round; None if none
    self._last_answered: the last frame number answered, to check that each
        question is for a newer frame
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._record = {}
        self.values_copied_while_paused = False
        self._owed_answer = None
        self._last_answered = None

    def record(self, qualified_name: str, attr_name: str, value: tuple) -> None:
        """Remember that `attr_name` of part `qualified_name` now holds
        `value`, a `(custom_class_name, values)` pair."""
        self._record.setdefault(qualified_name, {})[attr_name] = value

    def flush(self, channel: ThreadChannel) -> None:
        """Sends everything recorded since the last flush as one
        `SetAttributeCommand`, then starts a new record. Sends nothing when
        nothing was recorded, so a batch on the queue always means changes
        to apply.
        """
        if not self._record:
            return
        SimulationBridge.set_attributes(channel, self._record)
        self._record = {}

    def start_round(self, channel: ThreadChannel, update_pending: bool) -> None:
        """Called at the start of every round, before the events are drained
        and the values copied.

        First sends the previous round's batch, then "go" for the question
        that round took, in that order, so the simulation drains the batch
        before its next tick. Then, with lockstep enabled and an update
        pending, waits for the simulation's question: it has published and is
        blocked, so this round's values are copied while it is paused. Notes
        whether it waited; with lockstep disabled (nobody will ask, e.g.
        tests) it never waits.

        Waits without a timeout: while an update is pending the simulation
        asks within one frame. Raises RuntimeError if a question isn't for a
        newer frame than the last one answered.
        """
        self.flush(channel)
        if self._owed_answer is not None:
            channel.move_permission_queue.put(self._owed_answer)
            self._last_answered = self._owed_answer
            self._owed_answer = None

        if channel.lockstep_enabled and update_pending:
            frame = channel.move_request_queue.get()
            if self._last_answered is not None and frame <= self._last_answered:
                raise RuntimeError(
                    f"The simulation asked to move past frame {frame}, "
                    f"but frame {self._last_answered} was already answered")
            self._owed_answer = frame
            self.values_copied_while_paused = True
        else:
            self.values_copied_while_paused = False
