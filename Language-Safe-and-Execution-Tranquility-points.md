# Language Safe Points and Execution Tranquility Points — when a hot update may be applied in SysMLv2

Design record, not a task checklist. It captures the decision that, for the
SysMLv2 interpreter, "safe to apply an update" has **two independent layers**
that must both hold. Builds on the `Update` / `UpdatePoint` machinery
introduced in commit `49bbac0` ("Add update points and update definition +
testing with minilogo and sysmlv2"). No implementation started yet (no code
changes made as of this writing). Expected to grow: append new `## Topic N`
sections as the design is refined.

---

# Topic 1 — Two layers of safety

## The observation that started this

Commit `49bbac0` made the VM apply a pending `Update` (`core/edit.py`) only when
the running operation's syntax node is an `UpdatePoint` of the update's
`checkpoint_type()` *and* the update's `condition(runtime)` holds. For SysMLv2
it supplied:

- `StateUsage` marked as an `UpdateBeforePoint` (`languages/sysmlv2/syntax.py`,
  `class StateUsage`), so every state-machine reactive pass is a checkpoint;
- `QuiescentUpdate.condition` (`languages/sysmlv2/updates.py`): every
  `ExecutableStateUsage` settled in a substate with an empty `pending` mailbox.

That works for minilogo, where a single notion ("pen up") is both the place
where the interpreter is consistent and the place where the drawing makes sense
to change. It does not carry over to SysMLv2. A SysMLv2 program is
*interpreted* by LipVM and is *itself* a behavioural model with states of its
own. The interpreter being in a consistent place says nothing about whether the
modelled system is in a sensible place to change, and vice versa.

## The two layers

| | **Language safe point** | **Execution tranquility point** |
|---|---|---|
| Question it answers | Is the *interpreter* at a place in AST interpretation where swapping things will not corrupt its own bookkeeping? | Is the *modelled system* in a state where changing its behaviour makes sense in its domain? |
| Who defines it | The language engineer (author of the SysMLv2 interpreter) | The modeller, inside the `.sysml` model |
| Varies by | Language | Model |
| Example | "Between two reactive passes, not halfway through firing a transition (after `exit`, before `effect`/`entry`)" | "The conveyor is `Idle`," "the gripper is `Open` and holds nothing" |
| What breaks if ignored | Runtime is internally torn: e.g. `current` points at a target state whose entry action never ran | Runtime is internally consistent, but the physical/simulated system is mid-task: e.g. a part dropped mid-grip |

Naming note: *tranquility* follows Vandewoude et al., "Tranquility: A Low
Disruptive Alternative to Quiescence for Ensuring Safe Dynamic Updates" (IEEE
TSE, 2007), which proposed it as a weaker, more local alternative to Kramer &
Magee's *quiescence* ("The Evolving Philosophers Problem: Dynamic Change
Management", IEEE TSE, 1990). How closely this design follows Vandewoude's exact
definition, in particular its condition on adjacent components, is still open
(see Topic 3).

## The composed rule

A pending update is applied only when all three hold:

```
at a language safe point          -- interpreter-level, fixed per language
AND execution is tranquil         -- model-level, declared by the modeller
AND the update's own condition    -- optional, per Update (Update.condition)
```

The first two are properties of the language and of the model respectively.
The third stays available for update-specific gating (e.g. "only while the
gripper is `Open`") that neither the language nor the model declares generally.

---

# Topic 2 — How the current implementation maps onto the two layers

## Language safe point: correct in spirit, too broad in scope

`UpdateBeforePoint` on `StateUsage` is a language safe point: it says "before a
reactive pass". Two caveats:

- **Every** `StateUsage` becomes an update point, including substates nested in
  a `StateDefinition`, not just top-level ones like `main : MySimulationDefinition`.
  It is only correct today because the only stepped operation is
  `ExecutableStateUsage.evaluate`, whose `ast_node()` resolves to a top-level
  `StateUsage`. Nothing enforces that.
- The marking is on the **syntax class**. That is the right owner for a
  language-level property (the language engineer decides it once), but it means
  it cannot double as the model-level tranquility marking (Topic 3).

## Tranquility: currently a generic stand-in written in Python

`QuiescentUpdate.condition` ("settled in a substate, empty mailbox") is neither
layer cleanly:

- "Settled in a substate" largely restates the language safe point: at the
  start of a reactive pass the machine is never mid-transition anyway.
- "Empty mailbox" is a generic heuristic, the same for every model, and lives
  in `languages/sysmlv2/updates.py` rather than in the model.

Under this design it is replaced by a tranquility check driven by what the
modeller declared in the `.sysml` model. Whether an empty mailbox is
*additionally* required is an open question (Topic 3).

## Granularity limit of language safe points today

In the SysMLv2 interpreter the only `is_step` boundary is
`ExecutableStateUsage.evaluate` (`languages/sysmlv2/runtime.py`). A whole
reactive pass is one VM step; exit, effect and entry actions run as eager
sub-calls inside it. Consequently:

- the only language safe point the VM can reach today is **between reactive
  passes**;
- finer-grained safe points (e.g. "after the exit action, before the effect")
  would require changing the step granularity first.

Between passes is likely sufficient for a first version, but the limit should
be stated explicitly in the implementation.

## Adjacent issues in `49bbac0` that interact with this design

Recorded here because they affect any implementation of the composed rule; they
are not part of the two-layer decision itself.

- **AST/runtime drift.** SysMLv2 updates carry no `edit_script`; they mutate the
  runtime registry only. After a hot update the AST still describes the old
  behaviour, so a restart (or anything rebuilding from the AST) silently
  reverts it.
- **`VirtualMachine.update()` is untested for SysMLv2.** Tests set
  `vm._pending_update` directly. The public path ends in `self.run()`, which
  never returns for a reactive state machine. Its `RESTART` branch also calls
  `update.apply(runtime)` before the first step has built the registry, and
  never checks `condition()`.
- **`core/lesp.py` still passes an `EditScript`** to `VM.update(...)`, which now
  expects an `Update`.

---

# Topic 3 — Open questions

## How the modeller marks tranquility in the `.sysml` model

Leading candidate: SysMLv2 **metadata**, the language's own mechanism for
annotating model elements, e.g.

```sysml
metadata def Tranquil;

state def MySimulationDefinition {
    #Tranquil state Idle;
    state Next;
}
```

The metamodel classes (`MetadataUsage`, `MetadataDefinition`,
`MetadataFeature`) already exist in `languages/sysmlv2/syntax.py`; the
interpreter does not read them yet. Not yet confirmed that the XMI export
preserves the annotation in a form the loader picks up.

## What may be marked

Only states (e.g. `Idle`)? Or also transitions/actions, e.g. "not tranquil while
this action is running"?

## Scope of tranquility

Is a single state machine tranquil merely by being in a tranquil state, or must
every machine it interacts with also be tranquil (closer to Vandewoude's
definition)? Must *all* running `ExecutableStateUsage`s be tranquil, or only
those an update touches?

## Mailbox

Must `pending` also be empty, or is being in a tranquil state enough?

## Per model or per update

Is one tranquility marking used by every update, or may an update require its
own tranquility (beyond what `Update.condition` already allows)?

---

## Status

- Two-layer model (language safe point + execution tranquility point, plus
  optional per-update condition): **agreed**.
- Marking mechanism, scope, mailbox requirement, per-update override: **open**.
- No code changes made.
