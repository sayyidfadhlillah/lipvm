"""Step 1 of the tranquility work (Language-Safe-and-Execution-Tranquility-points.md,
Topic 8): the interpreter recognises constraints labelled `#Tranquility`
(LiveModeling::Tranquility) in complete-interesting-simulation.

Written ahead of the implementation. `syntax._is_tranquility_constraint` is
looked up on the module inside the test, not imported at the top, so that
until it exists that test fails on its own rather than the whole module
failing to collect.
"""

import types

import pytest

from core.language import Scenario
from core.vm import VirtualMachine

from languages.sysmlv2 import runtime as rt
from languages.sysmlv2 import syntax
from languages.sysmlv2.simulation_models.fischertechnik.enums import ConveyorCommandKind
from languages.sysmlv2.syntax import AssertConstraintUsage, ConstraintUsage
from languages.sysmlv2.sysml_utility_classes import qualified_name

from tools.load_xmi_with_syntax import load


XMI = "tests/complete-interesting-simulation.xmi"


# --- Helpers ---

def _build(root=None) -> VirtualMachine:
    """Load the model (or use the already loaded `root`) and run the build/registry pass."""
    vm = VirtualMachine()
    vm.scenario = Scenario(program_definition=root if root is not None else load(XMI).contents[0])
    vm.init()
    vm.step()
    return vm


def _owner(constraint) -> str:
    """Qualified name of the element owning `constraint` (through its FeatureMembership)."""
    return qualified_name(constraint.eContainer().eContainer())


def _part_def(vm: VirtualMachine, part_def_qualified_name: str):
    """The registry's rt.PartDef for `part_def_qualified_name`."""
    return vm.state.sysml.lookup_table_part_defs.get_reference(part_def_qualified_name).element_type


# --- Tests ---

def test_part_defs_with_tranquility_constraints_are_still_registered():
    vm = _build()
    part_defs = [record.qualified_name for record in vm.state.sysml.lookup_table_part_defs.records]
    assert "TokenProducerSystem::TokenProducer::TokenProducerMachine" in part_defs
    assert "TokenDepoSystem::TokenDepo::TokenDepoMachine" in part_defs
    assert "VacuumGripperSystem::VacuumGripper::VacuumGripperMachine" in part_defs
    assert "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine" in part_defs


def test_tranquility_metadata_definition_is_not_registered_as_item_def():
    vm = _build()
    item_defs = [record.qualified_name for record in vm.state.sysml.lookup_table_item_defs.records]
    assert "LiveModeling::Tranquility" not in item_defs


def test_recognises_the_four_part_def_tranquility_constraints():
    root = load(XMI).contents[0]
    tranquility = [element for element in root.eAllContents()
                   if isinstance(element, ConstraintUsage) and syntax._is_tranquility_constraint(element)]
    assert sorted(_owner(constraint) for constraint in tranquility) == [
        "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine",
        "TokenDepoSystem::TokenDepo::TokenDepoMachine",
        "TokenProducerSystem::TokenProducer::TokenProducerMachine",
        "VacuumGripperSystem::VacuumGripper::VacuumGripperMachine",
    ]


# --- Step 2: tranquility conditions in the runtime registry ---

def _assert_comparison(condition, attribute_qualified_name: str, operator: str, literal: str) -> None:
    """`condition` is `<attribute> <operator> <literal>`, e.g. `platformSens == false`."""
    assert isinstance(condition, rt.BinaryExpression)
    assert condition.operator == operator
    assert isinstance(condition.left, rt.ReferenceValue)
    assert condition.left.el.qualified_name == attribute_qualified_name
    assert isinstance(condition.right, rt.LiteralValue)
    assert condition.right.el == literal


def _assert_enum_comparison(condition, attribute_qualified_name: str, operator: str,
                            enum_literal_qualified_name: str) -> None:
    """`condition` is `<attribute> <operator> <enum literal>`, e.g.
    `currentCommand == ConveyorCommandKind::STOP`: an enum literal is a
    reference to the enum member, not a LiteralValue."""
    assert isinstance(condition, rt.BinaryExpression)
    assert condition.operator == operator
    assert isinstance(condition.left, rt.ReferenceValue)
    assert condition.left.el.qualified_name == attribute_qualified_name
    assert isinstance(condition.right, rt.ReferenceValue)
    assert condition.right.el.reference_type == "EnumerationUsage"
    assert condition.right.el.qualified_name == enum_literal_qualified_name


def _conjuncts(condition) -> list:
    """Flattens a chain of `and`s into its operands, left to right."""
    if isinstance(condition, rt.BinaryExpression) and condition.operator == "and":
        return _conjuncts(condition.left) + _conjuncts(condition.right)
    return [condition]


def test_part_defs_carry_their_tranquility_condition():
    vm = _build()

    # `#Tranquility constraint { platformSens == false }`
    producer = "TokenProducerSystem::TokenProducer::TokenProducerMachine"
    [condition] = _part_def(vm, producer).tranquility_conditions
    _assert_comparison(condition, f"{producer}::platformSens", "==", "False")

    # `#Tranquility constraint { receiverSens == false }`
    depo = "TokenDepoSystem::TokenDepo::TokenDepoMachine"
    [condition] = _part_def(vm, depo).tranquility_conditions
    _assert_comparison(condition, f"{depo}::receiverSens", "==", "False")

    # `#Tranquility constraint { verticalEncoder == 0.0 and armEncoder == 0.0 and
    #   rotEncoder == 0.0 and vacuumActCompressorOn == false and vacuumActValve == false }`
    vgr = "VacuumGripperSystem::VacuumGripper::VacuumGripperMachine"
    [condition] = _part_def(vm, vgr).tranquility_conditions
    comparisons = _conjuncts(condition)
    assert len(comparisons) == 5
    _assert_comparison(comparisons[0], f"{vgr}::verticalEncoder", "==", "0.0")
    _assert_comparison(comparisons[1], f"{vgr}::armEncoder", "==", "0.0")
    _assert_comparison(comparisons[2], f"{vgr}::rotEncoder", "==", "0.0")
    _assert_comparison(comparisons[3], f"{vgr}::vacuumActCompressorOn", "==", "False")
    _assert_comparison(comparisons[4], f"{vgr}::vacuumActValve", "==", "False")

    # `#Tranquility constraint { currentCommand == ConveyorCommandKind::STOP }`
    cb = "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine"
    [condition] = _part_def(vm, cb).tranquility_conditions
    _assert_enum_comparison(condition, f"{cb}::currentCommand", "==",
                            "ConveyorBeltSystem::ConveyorBeltCommands::ConveyorCommandKind::STOP")


def test_part_def_without_tranquility_constraint_has_no_condition():
    # `part def Machine;`, the abstract base of every machine.
    part_def = _part_def(_build(), "Common::Machine")
    assert list(part_def.tranquility_conditions) == []


def test_asserted_tranquility_constraint_is_ignored():
    # Tranquility must not be an invariant (Topic 6), so the interpreter only
    # picks up unasserted constraints. `#Tranquility assert constraint` passes
    # the export, but is ignored like any other unsupported use of the label.
    root = load(XMI).contents[0]
    depo = "TokenDepoSystem::TokenDepo::TokenDepoMachine"
    [constraint] = [element for element in root.eAllContents()
                    if isinstance(element, ConstraintUsage) and _owner(element) == depo]

    # Turn `#Tranquility constraint { receiverSens == false }` into
    # `#Tranquility assert constraint { receiverSens == false }`: same label and
    # expression, moved onto an AssertConstraintUsage in the constraint's place.
    asserted = AssertConstraintUsage()
    asserted.ownedRelationship.extend(list(constraint.ownedRelationship))
    membership = constraint.eContainer()
    membership.ownedRelatedElement.remove(constraint)
    membership.ownedRelatedElement.append(asserted)

    assert list(_part_def(_build(root), depo).tranquility_conditions) == []


# --- Step 3: evaluating tranquility for a part instance ---

TOKEN_DEPO = "Main::tokenDepo"
VGR = "Main::vgrPickProducer"
CB_FEEDER = "Main::cbFeeder"


def _token_depo_values(**overrides) -> types.SimpleNamespace:
    """A complete simulation-side value object for a TokenDepoMachine: every
    attribute the part def declares in SysML."""
    values = dict(tokenCount=0, receiverSens=False, currentCommand=None, placementCoordinate=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _vgr_values(**overrides) -> types.SimpleNamespace:
    """A complete simulation-side value object for a VacuumGripperMachine,
    at home with the vacuum off unless overridden."""
    values = dict(currentCommand=None, executionStatus=None,
                  verticalEncoder=0.0, armEncoder=0.0, rotEncoder=0.0,
                  expectedVerticalEncoderValue=0.0, expectedArmEncoderValue=0.0,
                  expectedRotationEncoderValue=0.0,
                  vacuumActCompressorOn=False, vacuumActValve=False, placementCoordinate=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _conveyor_belt_values(**overrides) -> types.SimpleNamespace:
    """A complete simulation-side value object for a ConveyorBeltMachine,
    stopped unless overridden."""
    values = dict(currentCommand=ConveyorCommandKind.STOP, direction=None,
                  currentStepCount=0, targetStepCount=0,
                  conveyorSensFeed=False, conveyorSensSwap=False, conveyorSensImpulse=0,
                  placementCoordinate=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _publish_and_refresh(vm: VirtualMachine, snapshot: dict) -> None:
    """Stand in for the simulation publishing `snapshot`, then refresh the
    part instantiations' observed values from it."""
    vm.state.channel.latest_snapshot.publish(snapshot)
    syntax.refresh_part_values(
        vm.state.channel,
        vm.state.sysml.lookup_table_part_defs,
        syntax.part_instantiations(vm.state.sysml.lookup_table_part_instantiations))


def _is_tranquil(vm: VirtualMachine, part_usage: str) -> bool:
    """Asks the part's part def whether that part instance is tranquil now."""
    part = vm.state.sysml.lookup_table_part_instantiations.get_reference(part_usage).element_type
    return _part_def(vm, part.part_def_origin.qualified_name).is_tranquil(part, vm.state)


def test_token_depo_is_tranquil_when_no_token_at_receiver():
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=False)})
    assert _is_tranquil(vm, TOKEN_DEPO) is True
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values(receiverSens=True)})
    assert _is_tranquil(vm, TOKEN_DEPO) is False


def test_evaluation_leaves_no_current_part_behind():
    # The part is only the evaluation context for the duration of the check.
    vm = _build()
    _publish_and_refresh(vm, {TOKEN_DEPO: _token_depo_values()})
    _is_tranquil(vm, TOKEN_DEPO)
    assert vm.state.execution_context.current_part is None


def test_vgr_is_tranquil_only_at_home_with_vacuum_off():
    vm = _build()
    _publish_and_refresh(vm, {VGR: _vgr_values()})
    assert _is_tranquil(vm, VGR) is True
    _publish_and_refresh(vm, {VGR: _vgr_values(armEncoder=31.5)})
    assert _is_tranquil(vm, VGR) is False
    _publish_and_refresh(vm, {VGR: _vgr_values(vacuumActValve=True)})
    assert _is_tranquil(vm, VGR) is False


def test_conveyor_belt_is_tranquil_only_when_stopped():
    vm = _build()
    _publish_and_refresh(vm, {CB_FEEDER: _conveyor_belt_values()})
    assert _is_tranquil(vm, CB_FEEDER) is True
    _publish_and_refresh(vm, {CB_FEEDER: _conveyor_belt_values(currentCommand=ConveyorCommandKind.MOVE_TO_SENSOR)})
    assert _is_tranquil(vm, CB_FEEDER) is False


def test_part_missing_from_snapshot_is_not_tranquil():
    # Startup: the simulation hasn't created the part yet, so it has no
    # observed values and tranquility can't be confirmed.
    vm = _build()
    _publish_and_refresh(vm, {})
    assert _is_tranquil(vm, TOKEN_DEPO) is False


def test_part_def_without_tranquility_conditions_raises():
    # Proposal, pending the step-4 decision on a default (always tranquil,
    # never tranquil, or error): refuse to answer rather than pick one silently.
    # Every part usage in the model is now typed by a part def with conditions,
    # so ask `Machine` (the abstract base, no conditions) about cbFeeder.
    vm = _build()
    cb_feeder = vm.state.sysml.lookup_table_part_instantiations.get_reference(CB_FEEDER).element_type
    with pytest.raises(ValueError, match="no tranquility conditions"):
        _part_def(vm, "Common::Machine").is_tranquil(cb_feeder, vm.state)
