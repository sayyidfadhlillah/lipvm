# CleanWatts Sim — Open Issues for SysML Modeling

Discussion doc, not a decision record — flags structural mismatches between
the fischertechnik SysML-authoring pattern and CityLearn's actual object
model, surfaced while building `cleanwatts_main_simulation.py`. See
`../../../../Architectural-Discussion.md` (Topic 1, "Minimal SysML-side model
needed to drive it") for where this line of thinking started, and
`CityLearn-Sim-Doc.md` in this same directory for the CityLearn terminology
these issues assume.

## Why these are issues at all

In the fischertechnik domain, the `.sysml` file is written first and is the
spec: a `part def X specializes Machine { attribute ...; perform action ...; }`
declares an interface, and a Python `PartSimulationModel` subclass is then
hand-built to satisfy it exactly, one class per part def, constructed from
scratch by `Factory.instantiate_machine(qualified_name, part_def_name, attrs)`.
The object model is *derived from* the SysML model.

For CleanWatts, the object model already exists and is fixed — it's
CityLearn's own class hierarchy (`Battery`, `PV`, `StorageTank`, `Charger`,
`ChargerSimulation`, `ElectricVehicle`, `Building`, `CityLearnEnv`), with
attribute names, constructor shapes, and action semantics outside our
control. The `.sysml` model has to be derived *from* that, reversing which
side is spec and which is implementation. That reversal surfaces three
concrete mismatches with the fischertechnik pattern, below.

## Issue 1 — `instantiate_machine`'s job shrinks: binding, not constructing

**Fischertechnik:** `Factory.instantiate_machine` builds a machine from
scratch off one `part_def_name` — looks up a `PartSimulationModel` subclass,
constructs it, sets initial attributes from `attrs`, registers it. Nothing
about the machine exists before this call.

**CityLearn:** buildings/devices already exist the moment `CityLearnEnv` is
constructed from a schema (`Architectural-Discussion.md`'s Topic 1 already
flagged this, lines 45-50). Concretely, in
`cleanwatts_main_simulation.py`, `build_device_spec_building`
constructs an entire `Building` — battery, PV, storage tank, and EV charger
together — in one call, because CityLearn's `Building.__init__` requires
`episode_tracker`/`weather`/`carbon_intensity`/`pricing` etc. to all be
supplied together, borrowed from a template building
(`cleanwatts_main_simulation.py:141-163`). There's no way to instantiate one
device in isolation and register it the way `instantiate_machine` registers
one `ConveyorBeltMachine` at a time.

**Open question:** does `instantiate_machine` for this domain end up binding
a SysML qualified name to a `Building` as a whole (one call per building,
covering all its devices at once), rather than one call per device the way
fischertechnik parts are each their own machine? If so, do individual
devices (battery, PV, storage) get separate SysML `part def`s at all, or do
they become attribute/sub-structure on one `Building` part def?

### Discussed 2026-09-11 — direction agreed, split into two milestones

Checked whether CityLearn's own "dynamic topology" mode
(`topology_mode='dynamic'`, `CityLearnTopologyService` in the installed
package) sidesteps this. It doesn't: its `add_member`/`add_asset` events are
schema-scripted (fixed `time_step`s declared before `CityLearnEnv` is
constructed, not called imperatively at runtime), and `add_member` only
clones a `Building` already present in the pool handed to `CityLearnEnv(
buildings=[...])` at construction — there's no path to hand it a brand-new,
just-instantiated device spec after the fact. It's also private API
(`_add_member`, underscore-prefixed), so leaning on it directly would couple
us to this installed version's internals. Ruled out as the mechanism.

Also relevant: LipVM already has a generic live-edit mechanism this should
plug into rather than reinvent — `core/vm.py`'s `ProgramUpdateOption.HOTSWAP`
+ `Update` (`core/edit.py:117-151`): a language subclasses `Update`,
declares `checkpoint_type()` (an `UpdatePoint`/`UpdateBeforePoint`/
`UpdateAfterPoint`, `core/language.py:138-175`) marking which AST node types
are safe to apply a change at, and overrides `apply(runtime)` with the
migration logic run once that checkpoint is reached. This is exactly the
seam a "SysML model changed while the simulation is ticking" scenario is
built for.

**Agreed direction**, as two implementation milestones:

- **Milestone 1 — get the simulation running at all.** `instantiate_machine`
  keeps doing real, full construction (Battery/PV/StorageTank/Charger/
  `Building` from SysML attrs, exactly as `build_device_spec_building`
  already proves out) into a pending registry, same idempotent-registration
  shape as `Factory._machines` today. The live `CityLearnEnv` is constructed
  lazily — once, from everything in the registry — right before the first
  tick, then `tick()` calls `env.step()` normally from then on. No dynamic
  topology, no hotswap handling yet; all buildings/devices instantiated
  before ticking starts. **Split into two sub-milestones** (discussed
  2026-09-11, driven by Issue 3's EV-ownership complexity below):
  - **1a — building-owned devices only.** `Battery`/`PV`/`StorageTank`/
    `Charger` construction and the lazy `Building`/`CityLearnEnv`
    bring-up, with none of Issue 3's EV-specific wrinkles (no
    `schema['electric_vehicles_def']` patching, no
    `associate_chargers_to_electric_vehicles` pairing, `Charger` present
    on the building but nothing ever connects to it). Gets the core
    lazy-construction mechanism proven and working in isolation first.
  - **1b — add the EV into the simulation.** Everything Issue 3 is about:
    the environment-owned `ElectricVehicle`, schema patching, and however
    that issue's ownership/association question gets resolved for SysML
    (own top-level part vs. something else). Deliberately sequenced after
    1a so the EV's non-containment, dynamically-associated shape doesn't
    have to be solved before the straightforward building-owned devices
    are even working.
- **Milestone 2 — hot-swap: add devices/buildings while already ticking.**
  A `CleanWattsUpdate(Update)` subclass with `checkpoint_type()` matching a
  tick boundary (never mid-`env.step()`). Its `apply(runtime)` rebuilds the
  live `CityLearnEnv` from the registry's current full contents: snapshot
  the specific scalars that need to survive from each already-live device
  (`soc`, `connected_electric_vehicle`, current `time_step` — not a blind
  deepcopy of the whole env, since `episode_tracker`/`time_step` bookkeeping
  should come fresh from the new construction), construct the new env with
  existing buildings reseeded via `initial_soc` from that snapshot plus any
  newly-instantiated buildings from the registry, `reset()`, then swap the
  simulation model's live env pointer. Controlled entirely from our own
  simulation-loop code — doesn't touch CityLearn's internals.
  - Open sub-question for when this milestone starts: time alignment for a
    rebuilt env's exogenous arrays (weather/carbon-intensity/price) against
    wherever the simulation actually is — `simulation_start_time_step`, or
    replaying `live_weather_and_carbon_intensity()` up to the current hour
    before resuming.

**Ruled out:** per-device `next_time_step()` does *not* offer a finer-grained
tick than `env.step()`. It exists on effectively every device (`Battery`,
`PV`, `StorageTank`/`DeferrableAppliance`/`Escalator`, `Charger`,
`ElectricVehicle`, `Building`, `CityLearnEnv`) but only because it's
inherited from `Environment.next_time_step()` (`base.py:257-266`), not
because any one device (e.g. `WashingMachine`) is special. It's called in a
synchronous cascade, not independently: `CityLearnEnv.next_time_step()` →
`runtime_service.next_time_step()` → every building's `next_time_step()` →
every one of *that* building's owned devices' `next_time_step()`, all inside
one `env.step()` call (`building.py:2676-2699`). Every device's internal
arrays are indexed by one shared `env.time_step` counter, so calling one
device's `next_time_step()` in isolation would desync its internal index
from everything else silently, not raise. Milestone 1/2 above stand as the
only real granularity CityLearn offers.

## Issue 2 — Actions aren't per-device method calls

**Fischertechnik:** each `perform action pick: Pick { in targetPosition: ... }`
in SysML maps to a same-named Python method (`vgr.pick(targetPosition=...)`),
called directly and individually via `Factory.execute_action(qualified_name,
action_name, args)`.

**CityLearn:** there is no per-device method call. Every controllable device
across every building is set via one batched normalized vector passed to a
single `env.step(actions)` call per timestep
(`cleanwatts_main_simulation.py:234-237`: `battery_action` is folded into
one `actions` list alongside a `0.0` placeholder for every other slot, then
`env.step(actions)` advances everything at once).
`Architectural-Discussion.md` lines 51-56 already anticipated this:
`execute_action` can only *stage* a value for a tick(), not execute
immediately.

### Discussed 2026-09-11 — two of the three original concerns dissolved, one real question remains

Originally framed this as three concerns: (1) no per-machine independent
pacing, (2) actions have no persistence across ticks, (3) actions write into
a shared vector rather than a per-device call. (1) and (2) don't hold up:

- **(1) dissolved.** `Factory.tick()` is already the single call that drives
  every fischertechnik machine forward each frame — CityLearn's `env.step()`
  plays the identical role. The per-machine `StepPacer`/`is_due()` pacing
  inside `Factory.tick()` exists to smooth *continuous visual movement*
  across rendered frames (fischertechnik's own comment: "0.5s per hop at
  60fps"), not because the SysML model itself needs independently-paced
  parts. CityLearn's hourly timestep has nothing analogous to pace — nothing
  is ever mid-motion the way a conveyor belt visually is. Not a real
  difference from what fischertechnik already does.
- **(2) dissolved, not by CleanWatts-specific staging, but by properly
  implementing SysML v2's own `do` action.** `StateUsage` already has a
  first-class `doAction` property in this codebase's metamodel
  (`languages/sysmlv2/syntax.py:6686` onward, the OMG SysML v2
  `entryAction`/`doAction`/`exitAction` triad) — `entry` runs once on
  entering a state, `do` runs for as long as the state stays active, `exit`
  runs once on leaving. `do` re-invoking every tick while its state is
  active is exactly "keep resubmitting this action" — not a gap CleanWatts
  needs bespoke machinery for, just `do` doing what it's already defined to
  do. **Not yet wired up in this codebase**, though: no fischertechnik
  `.sysml` example uses `do` (only `entry`), and `doAction`'s generated
  getter (`syntax.py:6750-6756`) still raises `NotImplementedError` in the
  generic scaffolding — so this is real, generic interpreter work
  (implement `do`'s re-invoke-while-active semantics), which CleanWatts then
  just uses, not something already functioning today.
- **(3) still real, narrowed scope.** `do` still has to write a value into a
  shared array read once per tick by one `env.step()` call covering every
  building/device at once — it can't call a method directly on one device in
  isolation the way `execute_action` calls `vgr.pick(...)` today. This is
  the one open piece of Issue 2 left to design.

**Open question, narrowed:** how does a `do` action (once implemented
generically) get from "this device's rate is 0.5" to "one shared array
handed to `env.step()`, with every other controllable slot defaulted to
`0.0` unless something else's `do` touched it this tick" — i.e. what does
the staging-buffer/action-vector-assembly architecture look like. Next
discussion topic.

## Issue 3 — EV ownership doesn't fit the Building-owned-part model

**Fischertechnik:** every machine is a peer, directly owned/instantiated,
referenced by other parts' state machines by name (e.g. `VGRMissionWith2CB`
takes `in feederCB` / `in transportCB` as parts passed in) — but each part
still has one clear owner that constructs and holds it.

**CityLearn:** the `Charger` is owned by the `Building`
(`building.electric_vehicle_chargers`), but the `ElectricVehicle` it connects
to is owned by the **environment**, not the building — sourced from
`schema['electric_vehicles_def']`, exposed as `env.electric_vehicles`
(`cleanwatts_main_simulation.py:205-210`). The two are paired *dynamically*,
every timestep, by CityLearn's own internal
`associate_chargers_to_electric_vehicles()` logic matching a
`ChargerSimulation` schedule's `electric_vehicle_id` string against that
pool by name — not by anything the interpreter/state-machine commands
interactively. See `CityLearn-Sim-Doc.md`'s "EV charger sub-layer" section
for the full three-way split (`Charger` / `ChargerSimulation` /
`ElectricVehicle`).

**Open question:** does the `ElectricVehicle` get its own top-level SysML
part (owned by something other than the `Building` part it interacts with),
with a non-containment association to the `Charger` part instead of
containment? Fischertechnik's `state def` pattern of taking other parts as
`in` parameters (rather than owning them) may be the closer precedent here
than `part def`/containment is.

### Discussed 2026-09-11 — sequencing decision, not yet a design answer

This issue's ownership question is exactly why Issue 1's Milestone 1 got
split into two sub-milestones (see above): **1a** covers only
building-owned devices (`Battery`/`PV`/`StorageTank`/`Charger`), with none
of this issue's EV-specific wrinkles — `Charger` exists on the building but
nothing connects to it yet. **1b** is where this issue's actual design
question (own top-level part vs. non-containment association, etc.) has to
get answered, deliberately sequenced after the simpler building-owned case
is already working. Doesn't resolve the open question above, just decides
when we're forced to.

## Status

Discussion only — no SysML or Python changes made for any of these yet.
