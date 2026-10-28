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
Management", IEEE TSE, 1990). Vandewoude's tranquility is a predicate over
runtime state, not a marking of program locations; how this design adapts it,
and which of its conditions are not yet covered, is recorded in Topic 4.

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

Two candidates: SysMLv2 **metadata** (below), or the **`constraint` /
`requirement`** constructs (Topic 5). Metadata is the language's own mechanism
for annotating model elements, e.g.

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

# Topic 4 — Vandewoude's tranquility vs. this design's adaptation

Consideration for further implementation. The definition below is summarised
from recollection of the paper and has **not yet been checked against the
original text**; verify the exact wording before relying on it.

## The original definition: a predicate over runtime state

Vandewoude et al. work at the level of component-based systems: *nodes*
(components) interact through *transactions*, sequences of interactions between
adjacent nodes. A node N is **tranquil** when:

1. N is not engaged in a transaction that it initiated;
2. N will not initiate new transactions;
3. N is not actively processing a request;
4. none of N's adjacent nodes is engaged in a transaction in which N has
   already participated and might still participate.

Compared with Kramer & Magee's quiescence, which additionally requires that no
other node will initiate a transaction needing N (in practice, passivating every
potential initiator), tranquility replaces that global requirement with the
local condition 4. It is less disruptive, but it is not guaranteed to be
reached; quiescence is the fallback. Once N is tranquil, the framework keeps it
tranquil by blocking new incoming requests for the duration of the update. The
paper's implementation is in the DRACO component framework.

Key point: tranquility is a **boolean condition on the runtime state** (which
transactions are in progress and who is involved). It does not annotate source
code or AST nodes.

## How this design adapts it

- **Marking elements in the model is our adaptation, not Vandewoude's.** With
  `#Tranquil state Idle` (Topic 3), the modeller marks SysMLv2 model elements,
  which are AST nodes from LipVM's point of view. The interpreter *derives* a
  predicate from those markings, e.g. "machine M is tranquil iff `M.current` is
  a state marked `#Tranquil`". The marking lives in the model, but its meaning
  is still a runtime condition, consistent with the original definition.
- **Condition 3 corresponds to the language safe point.** "Not actively
  processing a request" is, in the SysMLv2 interpreter, "not in the middle of a
  reactive pass". Vandewoude does not separate it into its own layer because
  the paper works at component level and never sees the interpreter; this
  design does (Topic 1).

## Concept mapping

| Vandewoude | SysMLv2 interpreter |
|---|---|
| node | an `ExecutableStateUsage` (one running state-machine instance) |
| transaction | an exchange of events between machines |
| condition 3 | between reactive passes (language safe point) |
| conditions 1, 2 and 4 | **not covered** by a tranquil-state marking alone |

## Gap to address in implementation

A tranquil-state marking captures "this machine is at rest". It does not
capture "this machine is waiting for a reply it asked for" (conditions 1, 2)
or "a neighbour is in the middle of an exchange with this machine" (condition 4).
The open questions on **scope** and **mailbox** in Topic 3 are really the
question of whether, and how, to cover conditions 1, 2 and 4. Doing so would
need the interpreter to know which event exchanges are in progress, which the
runtime does not track today: `pending` holds received events, but nothing
records outstanding exchanges between machines.

Also to decide: whether, as in the paper, tranquility must be *held* once
reached (e.g. by blocking event delivery to the machine until the update has
been applied), and what to do if it is never reached (wait indefinitely, time
out, or fall back to a stronger condition).

---

# Topic 5 — Defining tranquility with `constraint` or `requirement`

Initial insight: express tranquility in the model with SysMLv2's `constraint`
or `requirement` construct, rather than (or in addition to) tagging states with
metadata. Example syntax below is illustrative; attribute names such as
`isOpen` are hypothetical.

## The constructs

**Constraint.** A `constraint def` (`ConstraintDefinition`) is a reusable
*predicate*: a Boolean expression, optionally with input parameters. A
`constraint` usage (`ConstraintUsage`) instantiates it in a context, e.g.
inside a part, and evaluates to true or false. A plain constraint usage only
*describes* a condition; it claims nothing. Prefixing it with `assert`
(`AssertConstraintUsage`) claims it always holds, so the model is inconsistent
whenever it is false.

```sysml
constraint def GripperTranquil {
    in gripper : Gripper;
    gripper.isOpen and not gripper.isHolding
}
```

**Requirement.** A `requirement def` (`RequirementDefinition`) specialises
`ConstraintDefinition`, so it is also a predicate, with extra structure:

- a `subject`: the thing the requirement is about;
- `assume constraint`s and `require constraint`s: the requirement holds when the
  assumptions imply the required constraints;
- traceability: a short-name id (`<'T1'>`), `doc`, `stakeholder`/`actor`, and
  `satisfy <requirement> by <element>;` (`SatisfyRequirementUsage`) to claim that
  an element satisfies it.

```sysml
requirement def <'T1'> ConveyorTranquility {
    doc /* The conveyor may only be updated while it is idle and empty. */
    subject conveyor : ConveyorBelt;
    require constraint { conveyor.isIdle and conveyor.itemCount == 0 }
}
```

## Why they fit tranquility

- **Tranquility is a predicate over runtime state (Topic 4), and a constraint is
  SysMLv2's native predicate.** The definition then matches the concept, rather
  than a tag from which the interpreter infers a predicate, as with `#Tranquil`
  on a state.
- **More expressive than marking states.** A Boolean expression can combine
  attributes, states and parameters ("open *and* not holding"), which a
  per-state tag cannot. That is also the route by which some of Vandewoude's
  conditions 1, 2 and 4 could later be expressed, if the runtime exposes the
  needed information (Topic 4, "Gap to address in implementation").
- **Reusable and parameterised.** One `constraint def` can be applied to every
  instance of a part, the same way one `StateDef` serves several
  `ExecutableStateUsage`s.
- **A requirement's `subject` maps to Vandewoude's node.** It states which
  component the tranquility condition is about. This helps decide which running
  machine(s) must be tranquil for a given update (the scope question in Topic 3).
- **Requirements add traceability.** Id, documentation and `satisfy` links let
  the update-safety rule be reviewed and traced like any other system
  requirement. Framed this way, the requirement is on the *update process*:
  "the conveyor may only be updated while tranquil".

## Cautions

- **Do not assert the tranquility condition.** Tranquility holds only some of the
  time. `assert constraint`, or `satisfy` read as an invariant, would make the
  model inconsistent whenever the system is busy. The interpreter should
  *evaluate* the condition at language safe points, not treat it as an invariant.
- **The interpreter must be able to find it.** A constraint or requirement is not
  identified as "the tranquility condition" by itself. Options: tag it with
  metadata (`#Tranquility`), have it specialise a LipVM library definition
  (e.g. `constraint def TranquilityCondition`), or use a naming convention.
- **Referring to the active state.** Whether, and with what syntax, a SysMLv2
  expression can test "machine M is currently in state `Idle`" needs to be
  confirmed. If it cannot, the model would expose state through attributes, or
  LipVM would provide a library function for it.

## Interpreter support today

- The metamodel classes exist in `languages/sysmlv2/syntax.py`
  (`ConstraintDefinition`, `ConstraintUsage`, `AssertConstraintUsage`,
  `RequirementDefinition`, `RequirementUsage`, `SatisfyRequirementUsage`,
  `RequirementConstraintMembership`, `SubjectMembership`), but none of them has a
  `visit` or `evaluate` yet, so the interpreter currently ignores them.
- The runtime can already evaluate Boolean expressions at run time:
  `TransitionTriggerByWhenCondition.evaluate`, `BinaryExpression` and
  `AttributeReference` in `languages/sysmlv2/runtime.py` serve `when`
  conditions. A tranquility constraint could likely reuse that machinery.

---

# Topic 6 — Constraint or requirement for defining tranquility?

Comparison of the two candidates from Topic 5. Leaning: **unasserted
constraints** define tranquility; requirements are an optional later layer for
the update *policy*. Brainstorming still ongoing, not a final decision.

## Fit with the language

SysMLv2 distinguishes a *condition* from an *obligation*:

- An **unasserted constraint** is a Boolean condition that may or may not hold
  at a given moment. That is what tranquility is: true while the gripper is
  open and empty, false while it is gripping. Nothing is wrong when it is false.
- A **requirement** is a constraint plus intent: something the `subject` *shall*
  satisfy. Readers, verification cases and tools treat "not satisfied" as a
  problem. Tranquility is false most of the time by design, so modelling it as a
  requirement would read as "the gripper is out of spec whenever it is working",
  which is not the intended meaning.

Modelling style points the same way. Constraints usually sit inside the part or
state they describe, and their placement scopes them (e.g. a constraint inside
`state Idle { ... }` applies while the machine is in `Idle`). Requirements
usually sit apart from the structure and connect to it through `subject` and
`satisfy`; a requirement nested inside a substate would be unusual SysMLv2.

## Ease of implementation

| | Constraint | Requirement |
|---|---|---|
| AST to interpret | One Boolean expression | Subject binding, `assume`/`require` memberships, then "assumptions imply requirements" |
| Scoping | Follows from where it is placed | Must be resolved through `subject` / `satisfy` |
| Reuse of existing code | Close to how `when` conditions are already evaluated (Topic 5) | Same evaluation plus the extra layers above |

## Where a requirement does fit: the update policy

A requirement fits the *policy* rather than the *definition*:

```sysml
constraint def GripperTranquil { in g : Gripper; g.isOpen and not g.isHolding }

requirement <'U1'> safeGripperUpdate {
    doc /* The gripper shall only be updated while tranquil. */
    subject g : Gripper;
    require constraint : GripperTranquil { in g = safeGripperUpdate::g; }
}
```

The constraint answers "what is tranquility"; the requirement states "the update
process shall respect it", with id, documentation and traceability. That is a
genuine obligation, so the requirement is used for what it means. The binding
syntax above is a sketch and must be checked against the specification.

## No lock-in

A requirement is itself a constraint and can `require` an existing constraint.
Starting with constraints therefore does not prevent adding requirements later:
they can be layered on top without changing the tranquility definitions.

---

# Topic 7 — Brainstorm: scoping, alternatives, patterns, and a first-version scope

Brainstorm record following Topic 6. Example syntax is illustrative and must be
checked against the specification; attribute names such as `isOpen` are
hypothetical.

## Why a requirement makes instance scoping harder

A requirement does not take its scope from where it is placed. Two extra links
decide it:

1. `subject` names the *kind* of thing (`g : Gripper`), not which instances.
2. `satisfy ... by ...` connects it to actual elements, one statement per
   instance, possibly scattered over the model:
   ```sysml
   satisfy safeGripperUpdate by factory.gripper1;
   satisfy safeGripperUpdate by factory.gripper2;
   ```
   A `satisfy` inside a `part def` can cover every instance; the exact rule for
   what it binds to when `by` is omitted needs checking in the specification.

Consequences for the interpreter:

- It would have to scan the whole model for `satisfy` links and resolve each
  `by` target to a runtime instance, instead of reading the condition off its
  enclosing element.
- An instance covered by no `satisfy` is ambiguous: always tranquil, never
  tranquil, or a modelling error? (Under the defensive-validation preference,
  it should probably raise.)
- A requirement such as `safeGripperUpdate` concerns *updates*, which are Python
  `Update` objects, so a requirement-to-update mapping would also be needed.

Constraint placement already provides the same scopes:

| Want | With a constraint | With a requirement |
|---|---|---|
| All instances of a part | Constraint inside the `part def` | `satisfy` in the `part def` (rule to check) |
| One specific instance | Constraint inside that `part` usage | `satisfy ... by thatInstance` |
| Only while in a state | Constraint inside the substate | No direct equivalent |

Possible conclusion: the interpreter reads only constraints. Requirements, if
used, are documentation and traceability for people and tools; they do not
affect execution.

## Alternative constructs

Common limit: tranquility depends on runtime state, so the construct must hold
an expression evaluated at run time, not a static tag.

1. **Derived Boolean attribute.**
   `part def Gripper { attribute isTranquil : Boolean = isOpen and not isHolding; }`
   Simplest and reads naturally; other expressions can use it ("the factory is
   tranquil when all its grippers are"). Found only by name unless combined with
   pattern A. Less structured than a constraint (see "Attribute vs. constraint"
   below).
2. **Dedicated state region for the update lifecycle.** A parallel region
   (`Busy` / `Tranquil` / `Updating`) whose transitions the modeller controls;
   tranquility means "this region is in `Tranquil`". The only option that can
   also express *holding* tranquility once reached (an `Updating` state that
   delays events), as Vandewoude's framework does. Requires parallel
   (orthogonal) states: the metamodel has `StateDefinition.isParallel`, but the
   runtime does not execute parallel regions today. Most expensive option.
3. **Update protocol through ports and signals.** The component receives an
   `UpdateRequest` and replies `ReadyForUpdate` once it has brought itself to a
   tranquil state (e.g. finishes the current item, refuses new ones). Active
   rather than passive: the model drives itself to tranquility. Closest to the
   literature (Kramer & Magee's passivation; Vandewoude's conditions 1, 2, 4).
   Heaviest for modellers and interpreter; kept for later.
4. **Boolean `calc def`.** Works, since a constraint is essentially a calculation
   returning Boolean, but less idiomatic than a constraint.

Not suitable:

- **Metadata alone.** Metadata values must be evaluable from the model without
  running it, so metadata cannot hold a runtime condition. It can only label
  something that does (pattern B).
- **`concern`, `use case`, `verification case`, `snapshot`.** Not meant for
  runtime conditions.

## Patterns for using constraints and attributes

**A. LipVM library type to specialise.** Identification by typing rather than
naming convention:

```sysml
// provided by LipVM
abstract part def Updatable { constraint tranquility; }

// in the model
part def Gripper :> Updatable {
    constraint :>> tranquility : GripperTranquil { in g = self; }
}
```

The interpreter reads one known feature (`Updatable::tranquility`). A
redefinition on a `part` usage overrides it for a single instance. Whether a
missing definition defaults to tranquil or raises is to be decided (raising
fits the defensive-validation preference). The runtime already has
`AttributeRedefinition` for `:>>`, but it binds literal values only; expressions
would be new work. The same pattern works with an attribute
(`attribute isTranquil : Boolean`) or with a library
`constraint def TranquilityCondition` that model constraints are typed by.

**B. User-defined keyword (semantic metadata).** A library-defined keyword lets
the modeller write `#tranquility constraint gripperIdle { ... }`, automatically
tying the constraint to the library element. Same effect as A, nicer to read;
setup syntax to be checked.

**C. Hierarchical composition.** Each part defines its own tranquility; a
system-level expression combines them (the factory is tranquil when its conveyor
and grippers are). An update touching only the gripper checks only the gripper's
subtree. Addresses the scope question in Topic 3.

**D. Substate-scoped constraint.** `state Idle { constraint { ... } }` means
"tranquil while in `Idle`, provided that ...". Combines a state marking with a
condition; an empty `constraint { true }` is equivalent to tagging the state.
Relies on a constraint nested in a state applying only while that state is
active; to be confirmed in the Kernel Semantic Library (Occurrences).

**E. Requirement for update correctness.** If a requirement is used, a meaningful
role is `assume` tranquility, `require` that some invariant still holds after the
update. A verification-time statement about updates, not something the
interpreter executes.

## Attribute vs. constraint: expressiveness

Concern raised: a Boolean attribute may not be expressive enough for complex
tranquility conditions. Both use **the same expression language**, so neither is
more powerful for plain Boolean logic. The difference is structure:

| Need | Boolean attribute | Constraint |
|---|---|---|
| Long Boolean logic (`and`/`or`/`not`, comparisons, collection operations) | Same | Same |
| Parameters (reuse one condition for any gripper) | No, fixed to its owner | Yes, `constraint def GripperTranquil { in g : Gripper; ... }` |
| Decomposition into named sub-conditions | Awkward: separate attributes combined by hand | Nested constraints and local helper features |
| Reuse across unrelated parts or states | No | One definition, many usages |
| Specialisation and per-usage redefinition | Possible | More idiomatic |

A constraint usage is itself a Boolean-valued feature, so pattern A can use a
constraint as its hook, keeping both identification by typing and the structure
of a constraint.

Beyond either construct alone:

- **Time** ("idle for at least 2 s", "no event in the last N ticks").
- **History and in-progress exchanges** (Vandewoude's conditions 1, 2, 4), unless
  the runtime exposes them.
- **What the interpreter evaluates today**: binary expressions, literals and
  attribute references only. Anything beyond (`forAll`, function calls) is new
  work, whichever construct is chosen.

## Scope for now

- **Now:** complex logic over a part's or state machine's own attributes and
  parameters. Constraints are sufficient.
- **Later:** time. Two routes, both keeping constraints as the definition:
  - *Through state structure*: a substate reached by `accept after 2 [s]` from
    `Idle`, with the tranquility constraint placed in that substate ("idle for
    at least 2 s"). Standard SysMLv2, but the interpreter supports only signal
    and `when` triggers today; `after` is new work.
  - *Runtime-provided time values* ("time in current state", "time since last
    event") that constraint expressions can read.

## Fit with the existing interpreter

Based on how `when` conditions are evaluated today (`AttributeReference`,
`BinaryExpression`, `TransitionTriggerByWhenCondition` in
`languages/sysmlv2/runtime.py`):

- **Constraint in a `state def`, over its parameters: nearly free.**
  `AttributeReference` already resolves a parameter (e.g. `conveyorBelt`) against
  the running machine's bound arguments and reads the part's attribute from the
  simulation snapshot; `BinaryExpression` handles comparisons and `and`/`or`.
  `conveyorBelt.isIdle and conveyorBelt.itemCount == 0` has the same shape as an
  existing `accept when` condition.
- **Constraint in a `part def`, over the part's own attributes: not supported
  yet.** `AttributeReference` requires its target to be a parameter bound to a
  `PartInstantiation` (otherwise `NotImplementedError`); references relative to
  the part itself would be new work.
- **Evaluation context, for any placement.** Expressions resolve parameters
  through `runtime.execution_context`, which `ExecutableStateUsage.evaluate` sets
  at the start of each reactive pass. The VM checks a pending update *before* the
  step runs, when the context still belongs to the previous machine. The
  tranquility check must set the context for each machine it evaluates, or it
  will resolve parameters against the wrong machine.

## Suggested first version

A **constraint in a `state def`, over its parameters' attributes**, optionally
scoped to a substate (pattern D). It matches the current scope and reuses the
most existing machinery. Placement in `part def`, identification via a library
type (patterns A/B), and time follow later.

---

# Topic 8 — Decision for the first prototype: constraint + `#Tranquility` metadata

**Decided:** the first prototype defines tranquility with **unasserted
constraints**, and distinguishes tranquility constraints from ordinary ones with
a **`Tranquility` metadata** annotation. Example syntax is illustrative and must
be checked against the specification.

## Why metadata for identification

Labelling an element as special for tools and interpreters is what SysMLv2
metadata is for, and it does not change the constraint's meaning.

| | Metadata (`#Tranquility`) | Typing (`: TranquilityCondition`) | Naming convention |
|---|---|---|---|
| Changes the constraint's meaning | No, it is only a label | Yes, it specialises a library definition | No |
| Works on unnamed constraints and in any placement | Yes | Yes | No, needs a name |
| Can restrict where it is applied | Yes (see below) | Partly | No |
| Fragile | No | No | Yes: a typo silently turns it into an ordinary constraint |

## Sketch

```sysml
metadata def Tranquility {
    // only constraint usages may carry this label
    :> annotatedElement : SysML::ConstraintUsage;
}

state def ConveyorBehaviour {
    in conveyorBelt : ConveyorBelt;
    state Idle {
        #Tranquility constraint { conveyorBelt.isIdle and conveyorBelt.itemCount == 0 }
    }
}
```

The exact form of the `annotatedElement` restriction (`:>` vs. `:>>`) is to be
checked against the specification.

## Validation

- The `annotatedElement` restriction lets a SysMLv2 tool reject `#Tranquility`
  on anything other than a constraint usage.
- The interpreter checks it as well, and **raises** if `#Tranquility` labels:
  - an element that is not a constraint usage;
  - an *asserted* constraint (`assert constraint`), since tranquility must not
    be an invariant (Topic 6).

**Revised (2026-10-27): ignore rather than raise.** Our exporter
(`sysml-to-xmi-cli.jar`) does **not** enforce the `annotatedElement`
restriction: a throwaway model with `#Tranquility` on an attribute, an
`assert constraint`, a constraint in a `state def` and a constraint in a part
usage exported without error. For the research prototype the interpreter does
not raise either. It picks up only an **unasserted `#Tranquility` constraint
owned by a part def** and silently ignores every other use: the exporter may
accept it, the interpreter just doesn't act on it. **Revised (2026-10-28):** an
unasserted `#Tranquility` constraint owned by a **part usage** is picked up too,
and adds to the part def's conditions (see "Which tranquility conditions apply
to a part" below).

## To settle before implementing

1. **Does the metadata survive the XMI export?** Everything depends on this, so
   check it first: add `#Tranquility` to a small `.sysml` model, run it through
   the existing XMI conversion, and check that a `MetadataUsage` pointing at the
   constraint appears in the loaded resource.
2. **Where `metadata def Tranquility` lives.** Either in each model, or in a
   small shared LipVM library package that models import. Preferred for the
   prototype: the shared package, giving one definition whose qualified name the
   interpreter can match on.
3. **Interpreter support.** `MetadataUsage` and `MetadataDefinition` exist in
   `languages/sysmlv2/syntax.py` but have no `visit`; nor do the constraint
   classes (`ConstraintUsage`, `AssertConstraintUsage`, ...). Both need adding.

Placement for the prototype follows Topic 7's suggested first version: a
constraint in a `state def` over its parameters' attributes, optionally scoped to
a substate.

**Settled (implementation step 1, Topic 12):**

1. The metadata survives the XMI export: each `#Tranquility` constraint owns a
   `MetadataUsage` typed by the metadata definition.
2. `metadata def Tranquility` lives in a shared `library package LiveModeling`,
   which models import (`private import LiveModeling::*;`). The interpreter
   matches it by qualified name (`TRANQUILITY_METADATA` in `syntax.py`), not by
   the package being a library. Re-exporting after adding the `library`
   keyword changed only the package's type (`sysml:Package` →
   `sysml:LibraryPackage`), and the full suite still passed.
3. Interpreter support: `_is_tranquility_constraint` and
   `_tranquility_condition` in `syntax.py`.

Placement changed from the sketch: the constraints sit in **part defs**, over
the part's own attributes (e.g. `TokenDepoMachine`), not in a `state def`.

**Ignoring unsupported uses (see the revision under Validation):** done. A
non-constraint, and a constraint outside a part def, were already ignored. An
`assert constraint` is now ignored too: `_is_tranquility_constraint` rejects an
`AssertConstraintUsage` explicitly, since it is also a `ConstraintUsage`
(`test_asserted_tranquility_constraint_is_ignored`).

## Which tranquility conditions apply to a part

**Resolved (2026-10-28) by SysML v2's inheritance rules.** The question was:
once constraints may also sit on part usages, which conditions apply to a part
(part def only, usage overrides definition, or usage adds to definition), and
are a supertype's conditions inherited through part def specialization (e.g.
`ConveyorBeltMachine specializes Machine`)?

Checked against the metamodel documentation (generated into
`languages/sysmlv2/syntax.py`):

1. **Typing is a kind of specialization.** `FeatureTyping` is a subclass of
   `Specialization`: "FeatureTyping is Specialization in which the specific Type
   is a Feature. This means the set of instances of the (specific) typedFeature
   is a subset of the set of instances of the (general) type." So `tokenDepo`
   relates to `TokenDepoMachine` the way `ConveyorBeltMachine` relates to
   `Machine` (`Subclassification`, also a `Specialization`).
2. **A usage inherits its definition's constraints.** A type inherits "the
   non-private Memberships of all the supertypes of this Type", with "redefined
   Features removed" (`Type::inheritableMemberships`,
   `Type::inheritedMemberships`). A `#Tranquility` constraint in a part def is
   one of its features, so every usage typed by it inherits it, transitively
   through specialization as well.
3. **Per-machine evaluation is correct.** A `ConstraintUsage` is a
   `BooleanExpression`, a condition evaluated in the context of each instance;
   only an `AssertConstraintUsage` (also an `Invariant`) is asserted to be true
   for every instance, which is why asserted ones are ignored.

**The rule:** a part's tranquility conditions are its own plus every one it
inherits through typing and specialization, minus any it redefines.

- **Adding is the default:** a usage's own constraint comes on top of the
  inherited ones.
- **Overriding only through redefinition**, which needs a *named* constraint
  (`constraint :>> name { ... }`). `#Tranquility` constraints are anonymous
  today, so they can only accumulate.
- **Private constraints are not inherited:** a `private` `#Tranquility`
  constraint in a part def does not apply to its usages.

**Not decided by SysML, our interpretation layer:** "an update applies only
when *all* of a part's tranquility conditions are true". SysML only gives each
unasserted constraint a true/false result per instance.

**Consequence for the design:** the part, not its part def, answers "am I
tranquil?". `PartInstantiation.is_tranquil(runtime)` takes the conditions of
its part def (through `part_def_origin`) and evaluates them against itself;
supertypes are deferred, since the interpreter has no part def inheritance at
all yet (`ARCHITECTURAL-CONFUSION.md`, Topic 5); `PartDef` keeps only its conditions as data, and
`TranquilUpdate.condition()` asks each affected part directly. Today's code asks
only the direct part def (`<part def>.is_tranquil(part, runtime)`), so
conditions on a part def's supertypes would be missed; no machine part def has
a supertype with conditions yet (`Machine` has none), so behaviour is the same
for now.

**Implemented (2026-10-28):** `PartInstantiation` is a `TranquilityHolder`;
`PartUsage.visit` collects the usage's own `#Tranquility` constraints (lifting
step 1b's "ignore" for part usages), and `PartInstantiation.is_tranquil(runtime)`
evaluates its part def's conditions plus its own, all of which must hold
(`test_part_usage_carries_its_own_tranquility_condition`).
`TranquilUpdate.condition()` asks each affected part directly
(`part.is_tranquil(runtime)`); `PartDef.is_tranquil` refuses with a
`ValueError`, since only running parts are asked.

---

# Topic 9 — Selective tranquility per update, and incremental vs. atomic application

## Selective tranquility

Idea: rather than requiring every part to be tranquil for every update, the
**update's own edits decide which tranquility constraints matter**. If an update
only changes something in `TokenDepoMachine`, only `TokenDepoMachine`'s
`#Tranquility` constraint is checked; the VGR may be mid-grip.

Sketch, with the `Update` infrastructure from commit `49bbac0`:

1. Collect the AST nodes the update affects.
2. For each, walk up the containment tree to the enclosing `part def` and take
   its `#Tranquility` constraints.
3. Apply the update only when those constraints hold, for the instances of the
   affected part defs.

Scope for now: **part defs only**. Edits outside a part def (a `state def`, a
part usage, a shared enum) are left for later. How an update states which AST
nodes it affects is Topic 10.

## Incremental per-instance application and consistency

Initial idea: apply an update **incrementally**, to each instance as soon as that
instance becomes tranquil. Example: `TokenDepoMachine` has instances `depo1` and
`depo2`; `depo1` becomes tranquil and is updated while `depo2` is still busy.
This raises serious consistency problems:

1. **Two versions of one definition run at once.** All instances currently share
   one `rt.PartDef` record. Updating only `depo1` requires instances to point to
   different versions of their definition, which the registry does not support:
   a significant new mechanism.
2. **Old and new versions interact.** If the update changes how the part
   communicates (new or reinterpreted events, a changed action), the state
   machines and parts that talk to both depots see two behaviours at once, e.g.
   a VGR protocol written for the old version talking to a new-version depot.
   This is the core concern in the literature: Kramer & Magee's quiescence and
   Vandewoude's condition 4 exist to prevent an interaction from seeing a mix of
   versions. Ma et al. name the property **version consistency** ("Version-
   consistent Dynamic Reconfiguration of Component-based Distributed Systems",
   ESEC/FSE 2011): a transaction sees either all old or all new versions, never a
   mix.
3. **It may never finish.** If `depo2` never becomes tranquil, the system stays
   mixed indefinitely; a timeout or fallback policy is needed.
4. **No clean rollback.** If something fails partway, `depo1` is updated and
   `depo2` is not, with no single consistent state to return to.
5. **Behaviour depends on timing.** Which instance updates first depends on when
   each happens to become tranquil, making runs hard to reproduce and test.

**Atomic alternative:** wait until *all* instances of the affected part def are
tranquil at the same moment, then update them together. Consistent, but may wait
a long time.

**Middle ground:** the update declares its kind:

- *instance-local* changes (not affecting interactions, e.g. a threshold the part
  only uses internally) may be applied incrementally;
- *interaction-affecting* changes must be applied atomically.

This still needs version support in the registry for the incremental kind.

Suggested starting point: **atomic**, with incremental application as a later
extension. Not yet decided.

---

# Topic 10 — What an update targets, and construct-level SysMLv2 updates

Selective tranquility (Topic 9) needs to know, *before* applying an update,
which part defs it affects. This topic records what the current infrastructure
offers, and the direction for SysMLv2 update classes.

## Edit scripts cannot target a SysMLv2 model today

Checked on `tests/complete-interesting-simulation.xmi`:

1. **Every node has the same identifier.** An `EditSyntaxOperation` finds its
   target node by the integer `AbstractSyntaxElement.identifier`. The SysMLv2
   loader never sets it: all 2143 nodes have `identifier = 0`, so an edit
   operation cannot single out one node.
2. **`EditScript.attach_to` crashes.** It walks the tree with `get_children()`,
   which reads derived features the SysMLv2 classes leave unimplemented:
   `AttributeError: Operation not permited for "importedMembership" feature`
   (the same pitfall `Element.visit`'s docstring warns about).

This likely explains why the SysMLv2 updates in `languages/sysmlv2/updates.py`
leave `edit_script` empty and change the runtime registry directly.

## What the two update modes do with the old runtime state

- **`RESTART`: full replacement.** The edit script is applied to the AST and
  `init()` rebuilds the whole runtime state from scratch. Nothing compares old
  and new state. (For SysMLv2 this path does not work today, per the previous
  section.)
- **`HOTSWAP`: targeted, but opaque.** An update's `apply()` changes specific
  records of the existing registry in place (e.g. `RemessageTransitionEffect`
  changes one `Transition` argument). What it targets is known only inside its
  Python code: nothing can ask the update beforehand which records or part defs
  it will touch, and nothing records afterwards what changed.

## The targets are known, by convention

Each update's constructor arguments already locate its target in the old runtime
state. `RemessageTransitionEffect(state_def, source_substate, ...)` names the
transition whose argument it changes, and the same lookup `apply()` uses could
resolve that record before applying. But each class keeps this in its own private
fields (`_state_def`, `_source_substate`, ...), so the VM cannot ask uniformly.

## Options for stating what an update affects

- **A. Make edit scripts work for SysMLv2.** Unique `identifier`s at load time
  (the XMI's `elementId` is a UUID string while `identifier` is an integer, so a
  mapping is needed); `attach_to` walking only plain containment; rebuilding the
  affected registry records after an AST edit. The AST stays the source of truth
  and the AST/registry drift (Topic 2) goes away, but it touches the loader and
  the core `EditScript`: to agree with Valentin first.
- **B. The update declares its affected part defs** (e.g.
  `affected_part_defs()` returning qualified names). Simple, works with the
  current registry-only updates. The interpreter trusts the author; it should at
  least raise if a declared name is not a known part def. Does not fix the drift.
- **C. The update declares its affected AST nodes by qualified name**; the
  interpreter walks up to the enclosing part def (Topic 9's rule). Like B, at node
  level, and extends beyond part defs later.
- **D. Rebuild and compare.** Build a new registry from the changed model and
  compare it with the running one; differing records give the affected part defs,
  with nothing declared. Still needs a way to change the SysMLv2 model (A's
  problems) or to load a whole new version, a way to match records (e.g. by
  qualified name), and it says only *what* differs, not how to migrate the
  running state.

Leaning for the prototype: B or C, exposing the targets each update class already
knows through one common method.

## One update class per kind of change, named after the SysMLv2 construct

Following the existing pattern, each kind of change is an `Update` subclass whose
constructor names the target and whose `apply()` migrates the running state.
Classes are named after the **SysMLv2 construct** they change, not after a domain
operation: "move a part" is one *use* of a generic class, e.g.

```python
RedefineAttributeValue(
    part_usage="Main::tokenDepo",
    attribute="placementCoordinate",
    new_value=<FactoryCoordinate x=..., y=..., degrees=...>,
)
```

The same class would serve a thermostat setpoint or a CityLearn battery capacity.

Separation of concerns:

| Concern | Owner |
|---|---|
| *How* an attribute redefinition is changed (registry and simulation) | The generic update class (language level) |
| *Whether* it is safe to change it now | The part's `#Tranquility` constraint (model level) |
| *When* updates are considered at all | The checkpoint (`StateUsage`, before a reactive pass) |

Domain knowledge such as "do not move the conveyor while a token is on it"
belongs in the model's tranquility constraint, not in a `MoveConveyor` update.

## What `RedefineAttributeValue` must migrate

A part's attribute value lives in two places:

1. **The registry.** The part usage's `rt.PartInstantiation.attribute_redefinitions`
   (e.g. `placementCoordinate` as a `CompositeCustomValue`). `apply()` replaces
   the redefinition's value, the same way for any attribute.
2. **The simulation.** The simulated machine received the value once, when
   `PartInstantiation.evaluate` called `SimulationBridge.instantiate(...)`, which
   is idempotent (`Factory.instantiate_machine` does nothing for an
   already-registered part). The bridge offers only `instantiate`, `call_action`
   and `emit_event`: **no command changes an attribute of an existing machine**.
   A generic `set_attribute(qualified_name, attribute_name, value)` command is
   needed, converting the value the way `instantiate` already does through
   `CustomAttributeModel`. A simulation model that cannot change an attribute
   live should raise rather than silently ignore it.

The new value is a registry `Value` (`CompositeCustomValue` for a structured
attribute, `LiteralValue` for a scalar), keeping the update independent of domain
types. Unlike the existing SysMLv2 updates, which only change interpreter-side
behaviour, this one must migrate the simulation as well.

Tranquility: the target `Main::tokenDepo` is a part usage typed by
`TokenDepoMachine`, so only that part def's constraint applies (Topic 9), instead
of `QuiescentUpdate`'s "all machines settled, mailboxes empty".

## Open questions

1. **Usage vs. definition.** Changing a part usage's redefinition affects one
   instance; changing a part def's attribute default affects every instance and
   brings back incremental vs. atomic application (Topic 9). Likely two classes,
   e.g. `RedefineAttributeValue` (usage) and `ChangeAttributeDefault` (def).
   **Decided (2026-10-28), see "Runtime vs. design-time changes" below.**
2. **Missing redefinition.** If the part usage does not redefine the attribute
   yet (it uses the default), should the update add a redefinition, or raise?
   **Decided for the prototype: raise** (`LookupError`, listing what the usage
   does redefine).

## Runtime vs. design-time changes

**Decided (2026-10-28).** The model has two design-time layers above the
runtime model:

| Layer | Where | Example |
|---|---|---|
| Design-time: types | definition packages | `TokenDepoMachine`, its attributes and `#Tranquility` |
| Configuration of the running system | `Main` | `tokenDepo` at x=20.0 running `tokenDepoMission` |
| Runtime model | the interpreter's registry, connected to the simulation | `tokenDepo`'s `PartInstantiation`: configured and observed values |

The configuration in `Main` is causally connected to the running parts, so a
change to it is treated as a **runtime change**: the VM migrates the registry
and the simulation right away. A runtime change edits **configured** values
only (e.g. `placementCoordinate`); **observed** values (e.g. `receiverSens`)
are changed only by the simulation, never by an update. A change to a
definition is a **design-time change**: it propagates to every usage typed by
the definition that doesn't redefine the attribute (SysML's rule; to check
against the spec how `=` and `default =` interact with redefinition).

- **The level is in the update class's name**, e.g.
  `ChangeRuntimeAttributeValue`. The two levels migrate differently (one part
  vs. propagation), so they are separate classes, and the name states the
  scope. A design-time counterpart is added when needed. This revises the
  earlier idea of one `ChangeAttributeValue` interface for both owners.
- **What counts as runtime:** an owner the interpreter has a runtime record for
  (a `PartInstantiation`, an `ExecutableStateUsage`), i.e. what is actually
  running. Not the package name (`Main` is a convention of this model), and not
  usage vs. definition alone (usages also occur inside definitions, e.g.
  `perform action emitToken` in `TokenProducerMachine`).
- **Scope for now: runtime changes only.** `ChangeRuntimeAttributeValue` rejects
  a definition owner with a `ValueError` (it's a design-time change, not a
  missing feature of this class).

---

# Topic 11 — Three levels of responsibility for tranquility

## The idea

Modellers decide which constraints are tranquility conditions, but they can do so
only because the **language engineer** gives them a construct for it. In turn,
the **VM** must give language engineers an interface for offering such a
construct in their language. Each level provides a means of expression to the
level below:

| Level | Provides | To whom | In our case |
|---|---|---|---|
| **VM / framework** (`core/`) | An interface: how a language declares the way tranquility is defined in it | Language engineers | To design |
| **Language engineer** (`languages/sysmlv2/`) | A construct in the language for defining tranquility | Modellers | `#Tranquility` metadata on constraints |
| **Modeller** (`.sysml`) | The actual tranquility conditions | The running system | `#Tranquility constraint { platformSens == false }` |

## Contrast with language safe points

Language safe points have **two** levels. The VM provides `UpdatePoint`
(`UpdateBeforePoint` / `UpdateAfterPoint` in `core/language.py`), and the
language engineer decides directly that every `StateUsage` is one. The modeller
has no say.

Tranquility has **three**: the language engineer does not decide *which* nodes
are tranquility conditions, but *how modellers can say so*. A bare per-node query
in core (e.g. `AbstractSyntaxElement.isTranquilityCondition()`, default `False`)
lets a language *answer* whether a node is a tranquility condition, but does not
give the language engineer an interface for *defining* how modellers express it.
It is therefore not sufficient on its own.

## A possible shape for the core interface

1. **Class level, chosen by the language engineer:** "this construct of my
   language *can* define tranquility". E.g. a core abstract class (working name
   `TranquilityPoint`) that SysMLv2's `ConstraintUsage` extends, as `StateUsage`
   extends `UpdateBeforePoint`.
2. **Instance level, chosen by the modeller, with the rule set by the language
   engineer:** "this particular element *does* define tranquility". The language
   engineer implements the recognition rule: in SysMLv2, "labelled
   `#Tranquility`" (`_is_tranquility_constraint`); another language could use a
   keyword or a naming rule. Class-based marking alone cannot express this, since
   only *some* `ConstraintUsage`s are tranquility conditions.
3. **What else the language engineer provides**, so the VM can use the modeller's
   definitions without knowing the language:
   - **scope:** which program element a condition applies to (in SysMLv2, the
     enclosing `part def`), so the VM can select the relevant conditions for an
     update (Topic 9);
   - **evaluation:** whether the condition holds now, against the running state,
     for a given instance.

The interface would say to a language engineer: *make the constructs you offer
extend `TranquilityPoint`; tell the VM how to recognise which instances the
modeller marked, what each applies to, and how to evaluate it.*

## Relation to the runtime side

In SysMLv2, behaviour runs off the runtime registry, so the VM cannot evaluate an
AST node directly. The built, evaluable conditions live on runtime records; the
idea of an abstract runtime class (working name `TranquilityHolder`) that runtime
records with tranquility extend, holding `tranquility_conditions`, fits here as
the language engineer's runtime counterpart. A link from the marked AST node to
its runtime condition is needed, similar to `RuntimeStateElement.ast_node()`
linking runtime records back to AST nodes.

## Open points

- The exact core interface (class and method names, signatures). The evaluation
  signature must allow different "instances" per construct: a part def is
  evaluated per `PartInstantiation`, a state-level condition per running state
  machine.
- This changes `core/language.py`, Valentin's code: to discuss with him.
- Sequencing relative to steps 2 and 3, which this restructures.

---

# Topic 12 — Evaluating tranquility, and where part attribute values come from

## Context: the implementation steps

The prototype is built in steps, each test-first (`tests/test_sysmlv2_tranquility.py`):

1. **Recognise** `#Tranquility` constraints (`_is_tranquility_constraint` in
   `syntax.py`; `LiveModeling::Tranquility` no longer registered as an item def).
   Done.
2. **Store** each part def's conditions on its runtime record: the abstract
   runtime class `TranquilityHolder` (`runtime.py`) holds `tranquility_conditions`,
   `PartDef` extends it, and `PartDefinition.visit` builds the conditions with the
   existing `_build_expression`. Done.
3. **Evaluate** the conditions for one part instance: "is `Main::tokenDepo`
   tranquil right now?". `TranquilityHolder.is_tranquil`,
   `ExecutionContext.current_part`, and the `ReferenceValue` "AttributeUsage"
   branch (`runtime.py`). Done.
4. **Connect** tranquility to updates (Topics 9, 10).

## Step 3 decisions

- **Entry point:** `part_def.is_tranquil(part_instantiation, runtime)` on the
  part's `rt.PartDef` (via `TranquilityHolder`).
- **Passing the current part:** `Value.evaluate(runtime)` takes no instance
  parameter; other context already lives on `runtime.execution_context` (an
  `ExecutionContext` runtime element holding the current state machine). The
  check puts the part into that context for its duration (e.g.
  `execution_context.current_part`) rather than adding an instance parameter to
  every `Value` subclass. A bare attribute name in a condition, built as a
  `ReferenceValue` tagged `AttributeUsage` (e.g. `platformSens`), resolves
  against that part.
- **Several conditions on one part def:** all must hold.
- **Part not yet in the simulation** (startup: the simulation has not created
  it yet): the check answers **not tranquil** rather than raising. Tranquility
  cannot be confirmed yet; a later check gives a real answer.
- **Part def without conditions** (e.g. `Common::Machine`): **decided in step 4:
  always tranquil.** A live update must satisfy both layers, the language safe
  point and execution tranquility. Leaving out `#Tranquility` is the modeller's
  choice to accept possible inconsistency in the simulation, so only language
  safety is enforced: the update still waits for a language safe point, but the
  tranquility layer is trivially satisfied. Rejected alternatives: *never
  tranquil* (the update may wait forever) and *error at submission* (overrides
  the modeller's intent). Consequence: a `#Tranquility` constraint that fails to
  resolve (e.g. a missing `private import LiveModeling::*;`) now means "always
  tranquil" instead of an error. No interpreter guard for this: an unresolved
  name is a static modelling error that the SysML IDE reports while editing (the
  exporter also warns), so it is left to the modelling tools.

## Bare attribute names, no `self` or `this`

**Decided:** conditions refer to the part's attributes by bare name
(`receiverSens == false`), not through `self` or `this`.

- **It is valid SysMLv2.** Names resolve through the enclosing namespaces,
  including inherited members, so `receiverSens` resolves to the part def's
  attribute. The constraint is a feature of the part def, so it is evaluated
  against the part instance. The official training material uses the same
  form, e.g. `assert constraint {totalMass == chassisMass + engine.mass +
  transmission.mass}` inside a part:
  - [Derivation Constraints.sysml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml/src/training/31.%20Constraints/Derivation%20Constraints.sysml)
  - [Constraint Assertions-1.sysml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml/src/training/31.%20Constraints/Constraint%20Assertions-1.sysml)

  These examples are asserted constraints; ours are unasserted (Topic 6), which
  does not change name resolution.
- **`self` and `this` are not keywords.** They are standard-library features
  (`self` on `Anything`, `this` on occurrences), also resolved by scope. Inside
  a constraint body, `self` may well resolve to the constraint itself rather
  than the part, so they add a dependency on library rules without making the
  model clearer.
- **The implicit context is made explicit in the interpreter:**
  `ExecutionContext.current_part`, which a bare `AttributeUsage` reference
  resolves against, and which raises when it is unset.

Alternatives considered, if explicitness in the model becomes a goal:

- An `in` parameter typed by the part def (`in machine : TokenDepoMachine;
  machine.receiverSens == false`), bound by the interpreter.
- `SemanticMetadata` in `LiveModeling`, whose `baseType` gives every
  `#Tranquility` constraint an inherited `target` parameter. Editor/XMI support
  for the implicit specialisation is unverified.

**Debt:** `ReferenceValue` looks the attribute up by its **short name**, not by
the feature itself. That works for inherited constraints and for redefinitions
that keep the name (`:>> receiverSens`). It would break if a subtype redefined
the attribute under a different name.

## Where attribute values come from today

- The runtime record of a part usage, `rt.PartInstantiation`, holds **no live
  attribute values**.
- Each VM round, `Namespace.read_events_and_execute` (`syntax.py`) loops over
  every `PartInstantiation` and calls `evaluate()`, which only makes sure the
  part **exists** in the simulation (`SimulationBridge.instantiate(...)`,
  idempotent). Then `drain_event_queue(...)` delivers the simulation's events to
  the state machines' mailboxes, then the state machines run.
- The only snapshot refresh is `ExecutionContext.begin()` (`runtime.py`), at the
  start of **each state machine's pass**: it stores
  `channel.latest_snapshot.read()` in `execution_context.current_snapshot`.
- `AttributeReference.evaluate` (`runtime.py`), used by `accept when`
  conditions, reads attributes from that stored snapshot through
  `SimulationBridge.read_attribute_from_snapshot(...)`.

Consequence: two state machines in the same round can see different moments if
the simulation publishes between their passes.

Implementing step 3 on this design would require: capturing one snapshot per
check and passing it along (to avoid reading different moments within one
compound condition), handling `PartNotReadyError` during evaluation, sharing one
snapshot across several parts once updates check them together (Topic 9), and
teaching `ReferenceValue` to read through `SimulationBridge`.

## models@runtime design: part values on the part instantiations

1. **`Value.evaluate()` reads values from the runtime element instances**, the
   `PartInstantiation`s in the lookup table, not through `SimulationBridge`. In
   models@runtime terms, the registry becomes a runtime model causally connected
   to the simulated system.
2. **A per-round refresh copies the simulation's values onto the
   `PartInstantiation`s**, following the pattern of `drain_event_queue`:

   | | `drain_event_queue` (exists) | Refreshing part values (new) |
   |---|---|---|
   | Called from | `read_events_and_execute`, once per round | The same place, once per round |
   | Reads from the channel | `channel.event_queue` | `channel.latest_snapshot.read()`, **once** per round |
   | Resolves against the registry | Event name → `ItemDef` | Part qualified name → `PartInstantiation` |
   | Writes into registry records | `ExecutableStateUsage.pending` | The part instance's attribute values |

   Only the interpreter thread writes the registry; the simulation thread only
   publishes to the channel, as with events.

   ```python
   def refresh_part_values(channel, part_instantiations) -> None:
       snapshot = channel.latest_snapshot.read()          # one moment for the whole round
       for part in part_instantiations:
           if snapshot is None or part.qualified_name not in snapshot:
               continue                                    # not created in the simulation yet
           live = snapshot[part.qualified_name]
           part.observed_values = {name: getattr(live, name) for name in <its part def's declared attributes>}
   ```

3. **Placement:** in `read_events_and_execute`, **after** `drain_event_queue` and
   **before** the state machines run. The event queue and the snapshot are
   separate channels with no ordering guarantee; this placement means machines
   react to events while seeing values at least as recent as those events.

Differences from draining events:

- **A copy, not a drain.** Events are consumed once; a snapshot is state. The
  refresh overwrites previous values with the latest; if nothing new was
  published, they stay the same.
- **A part missing from the snapshot is normal at startup.** It keeps no values,
  without a warning; for tranquility it is not tranquil.
- **Only the attributes the part def declares in SysML are copied**
  (`rt.PartDef.attributes`). If the snapshot lacks a declared attribute, the
  refresh **raises**, as the simulation side's `PartSimulationModel.snapshot()`
  already fails loudly on a missing field.

**The SysML part def is the interface.** Its declared attributes are what the
model, and therefore `when` and tranquility conditions, can see. A simulation's
snapshot may hold **more** (physics values, timers, debug fields: internals the
interpreter never sees), never **less**. Checked against
`complete-interesting-simulation` and the Fischertechnik simulation models'
`snapshot_type` dataclasses: `TokenProducerMachine` (4 attributes),
`TokenDepoMachine` (4), `ConveyorBeltMachine` (8) and `VacuumGripperMachine` (11)
match exactly, nothing missing and nothing extra, so raising on a missing
attribute does not break existing runs. (`Machine` has no simulation model; it is
only the abstract base.)

**Behaviour change for `when` conditions** once they read the copied values:
today each state machine captures its own snapshot; with one refresh per round,
all machines in a round see the **same** values. More consistent, but a semantic
change that existing DT-simulation tests may notice. `ExecutionContext.begin()`
would no longer need to capture a snapshot.

## Order: models@runtime first, then step 3

- **Step 3 first, on the current design:** step 3 handles all the snapshot
  plumbing listed above; switching to models@runtime later rewrites the same
  read path and the step-3 tests again.
- **models@runtime first:** a self-contained change (one refresh function, one
  call, a field on `PartInstantiation`). Step 3 then shrinks: a bare attribute
  reads the current part's values, and "not in the simulation yet" means "no
  values yet". Step-3 tests set the part's values directly instead of publishing
  snapshots.

Decided: **models@runtime first, split in two parts**:

- **Part A, add the values:** the per-round refresh onto the
  `PartInstantiation`s. Nothing existing reads them yet, so `when` conditions
  keep reading the snapshot and **nothing existing changes behaviour**.
- **Part B, switch the readers:** `AttributeReference` (`when` conditions) reads
  the copied values instead of the snapshot. Done later, as its own change,
  since it causes the behaviour change above.

Sequence: **Part A → step 3 (tranquility reads the copied values) → Part B**.
Until Part B, `when` conditions read the snapshot while tranquility reads the
copied values, so within one round they may see slightly different moments;
acceptable for the prototype.

**Part B done.** `AttributeReference.evaluate` reads
`PartInstantiation.observed_value(name)`; `ExecutionContext.current_snapshot`
and `SimulationBridge.read_attribute_from_snapshot` are removed, and
`ExecutionContext.begin()` only records the running state machine. `when`
conditions and tranquility now read the same values within a round. No existing
test relied on the per-machine snapshot.

## Representation of the copied values: a mirror, separate from configuration

The copied values are a **mirror**: each round they reflect what the simulation
published, and the interpreter only reads them.

**Not in `attribute_redefinitions`.** A part instantiation's
`attribute_redefinitions` hold what the **model says** at a part usage (the `:>>`
redefinitions in `Main`, e.g. `tokenDepo`'s `placementCoordinate`): *configured*
values, flowing registry → simulation at instantiation, and changed by Topic 10's
`RedefineAttributeValue` update. Mirroring into them would be wrong:

1. They only cover redefined attributes (`tokenDepo` redefines
   `placementCoordinate` only; there is nothing for `receiverSens`).
2. Mirroring would overwrite the configuration every round. The configured value
   ("where the model says the part is") and the observed one ("where the
   simulation says it is now") can differ, e.g. while a `RedefineAttributeValue`
   update waits for tranquility.
3. It conflates model and state: a redefinition is a statement in the model, an
   observation is a fact about the running system. models@runtime needs both.

**Options for a separate mirror:**

- **Plain Python dict** on `PartInstantiation` (e.g. `observed_values`). Fits how
  evaluation already works: `LiteralValue` stores a string and converts it to a
  Python `bool`/`int`/`float` at evaluation, precisely to compare against live
  Python values; `BinaryExpression` compares Python values; the snapshot already
  holds Python values, including Python enums, which enum literals in conditions
  already resolve to. Precedent: `ExecutionContext` keeps plain Python attributes
  on a runtime element. Not part of the pyecore model: invisible to reflection
  and not serialisable to XMI.
- **Reflective pyecore mirror**: e.g. an `ObservedAttribute` record (name plus a
  contained `Value`) in a `PartInstantiation.observed_attributes` containment,
  created on the first refresh and updated in place afterwards. Scalars as
  `LiteralValue`, structured values as `CompositeCustomValue`; enums need a new
  representation (`ScalarType` has no enum kind).

**Runtime cost is not a deciding factor.** Measured at this model's size (7 part
instances, 57 declared attributes): refreshing the dict takes about 2.6 µs per
round and the in-place pyecore mirror about 117 µs; one read about 0.04 µs vs.
0.43 µs. The Fischertechnik visualisation ticks at 60 fps (16.7 ms per tick), so
even the pyecore mirror uses under 1 % of a tick. The real difference is
implementation effort: a one-line copy vs. a new class, value conversions both
ways, and an enum representation.

**XMI reflection needs more than the mirror.** Saving the runtime registry
(`vm.state.sysml`) to XMI after the build pass "succeeds", but writes only the
lookup tables' skeleton: all 70 records have an empty `element_type`, and no
`PartDef`, `PartInstantiation`, attribute redefinition or tranquility condition
appears. `Record.element_type` is `containment=False`, so the registry's elements
are referenced by the lookup tables but contained by nothing. Reflecting the
runtime model to XMI therefore also requires:

1. registry containment: the elements contained somewhere (e.g.
   `Record.element_type` as a containment, if each element is registered in
   exactly one table, or a dedicated container);
2. the AST resource saved in the same resource set, so runtime records'
   references to AST nodes (`definition`) serialise;
3. no plain Python attributes for anything that must be saved (this also applies
   to `ExecutionContext`).

**Decided: plain dict now, reflective mirror later.** Tranquility only needs to
read current values at the moment of a check; nothing in steps 3–4 saves, reloads
or inspects the runtime model as XMI. To keep the later switch cheap:

1. **One accessor.** All readers (tranquility now, `AttributeReference` in
   Part B) go through `PartInstantiation.observed_value(name)`, never the dict.
   Switching representation then changes only the refresh and that method.
2. **Tests go through the refresh.** Tests publish a snapshot and call the
   refresh, rather than writing the dict directly, so they also test the refresh
   and work unchanged with either representation.
3. **Recorded debt:** reflective pyecore mirror plus the registry containment fix
   (points 1–3 above), when XMI reflection of the runtime model becomes a goal.
4. **Declared, not ad hoc.** The dict lives in a declared pyecore attribute,
   `PartInstantiation.observed_values` (`EAttribute` of the `ObservedValues`
   data type, `eType=dict`, `transient=True`), not a plain attribute assigned in
   `__init__`. The structure is visible in the class and in its `eClass`, pyecore
   rejects non-dict values, and `transient` states that it isn't saved.

## Open points

- Keeping *observed* values (simulation → registry, every round) clearly separate
  from *configured* ones (attribute redefinitions, registry → simulation at
  instantiation and through the `set_attribute` command of Topic 10), so writing
  an observed value is never mistaken for controlling the machine. The separate
  dict and accessor already keep them apart structurally; naming and
  documentation should make it explicit.
- ~~The step-3 tests currently publish a snapshot and call `is_tranquil`
  directly; they must also call the refresh (decision point 2 above).~~
  Resolved: they publish and refresh (`_publish_and_refresh`).

---

## Status

- Two-layer model (language safe point + execution tranquility point, plus
  optional per-update condition): **agreed**.
- Marking mechanism, scope, mailbox requirement, per-update override: **open**.
- Coverage of Vandewoude's conditions 1, 2 and 4, holding tranquility once
  reached, and the fallback when it is never reached: **open** (Topic 4).
- Topic 4's summary of the paper: **to be verified** against the original text.
- Defining tranquility with `constraint`/`requirement` (Topic 5): **initial
  insight, under consideration**; how the interpreter identifies the condition
  and how to test the active state are **open**.
- Constraint vs. requirement (Topic 6): **leaning towards unasserted
  constraints** for the definition, with requirements as an optional later
  layer for the update policy; still brainstorming. Where to place the
  constraint (package, part def/usage, state def/usage, substate) is **open**.
- Scope (Topic 7): complex logic over own attributes/parameters **now**; time
  **later**. Suggested first version: constraint in a `state def` over its
  parameters, optionally substate-scoped; **not yet decided**. Identification
  mechanism (library type, keyword) and the alternative constructs (lifecycle
  region, update protocol) are **open / deferred**.
- First prototype (Topic 8): **decided and implemented**: unasserted
  constraints, identified by `#Tranquility` metadata from
  `library package LiveModeling`, placed in part defs. The metadata survives the
  XMI export. **Revised:** unsupported uses are ignored rather than raised on,
  and the exporter doesn't enforce the `annotatedElement` restriction. Ignoring
  an `assert constraint`: **done**. Which conditions apply to a part:
  **resolved by SysML v2 inheritance** (own plus inherited through typing and
  specialization, minus redefined); the part answers "am I tranquil?" itself
  (**implemented**, including a part usage's own conditions).
- Selective tranquility per update (Topic 9): **direction agreed**, scoped to
  part defs for now. Incremental vs. atomic application: **open**, suggested
  start is atomic. How an update states its affected AST nodes: Topic 10.
- Update targets and construct-level updates (Topic 10): **agreed** that SysMLv2
  update classes are named after constructs (e.g. `RedefineAttributeValue`), not
  domain operations. How an update states what it affects: **leaning B or C**.
  Open: usage vs. definition classes, missing redefinitions, and a new
  `set_attribute` bridge command for the simulation.
- Three levels of responsibility (Topic 11): **agreed**: the VM provides an
  interface to language engineers, who provide a construct to modellers. Exact
  core interface, discussion with Valentin, and sequencing with steps 2–3:
  **open**.
- Evaluation and attribute values (Topic 12): steps 1–3 **done**, Part A
  **done**, Part B **done** (`AttributeReference` reads `observed_value`;
  `ExecutionContext` no longer captures a snapshot). **Decided:** copied values
  as a plain dict in a declared, transient attribute, behind
  `PartInstantiation.observed_value(name)`, tests going through the refresh.
  **Gap:** a part that drops out of a later snapshot keeps its last observed
  values (`refresh_part_values` skips it); nothing removes parts today.
  **Decided:** conditions use bare attribute names, no `self`/`this` (valid
  SysMLv2, with evidence in Topic 12). **Decided (step 4):** a part def
  without conditions is always tranquil; only the language safe point applies.
  **Debt:** reflective pyecore mirror plus registry containment fix when XMI
  reflection of the runtime model is needed (today the registry saves to XMI
  as an empty skeleton); attribute lookup by short name breaks under a
  renaming redefinition.
