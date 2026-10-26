"""Step 1 of the tranquility work (Language-Safe-and-Execution-Tranquility-points.md,
Topic 8): the interpreter recognises constraints labelled `#Tranquility`
(LiveModeling::Tranquility) in complete-interesting-simulation.

Written ahead of the implementation. `syntax._is_tranquility_constraint` is
looked up on the module inside the test, not imported at the top, so that
until it exists that test fails on its own rather than the whole module
failing to collect.
"""

import types

from core.language import Scenario
from core.vm import VirtualMachine

from languages.sysmlv2 import runtime as rt
from languages.sysmlv2 import syntax
from languages.sysmlv2.syntax import ConstraintUsage
from languages.sysmlv2.sysml_utility_classes import qualified_name

from tools.load_xmi_with_syntax import load


XMI = "tests/complete-interesting-simulation.xmi"


# --- Helpers ---

def _build() -> VirtualMachine:
    """Load the model and run the build/registry pass."""
    vm = VirtualMachine()
    vm.scenario = Scenario(program_definition=load(XMI).contents[0])
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


def test_tranquility_metadata_definition_is_not_registered_as_item_def():
    vm = _build()
    item_defs = [record.qualified_name for record in vm.state.sysml.lookup_table_item_defs.records]
    assert "LiveModeling::Tranquility" not in item_defs


def test_recognises_the_three_part_def_tranquility_constraints():
    root = load(XMI).contents[0]
    tranquility = [element for element in root.eAllContents()
                   if isinstance(element, ConstraintUsage) and syntax._is_tranquility_constraint(element)]
    assert sorted(_owner(constraint) for constraint in tranquility) == [
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


def test_part_def_without_tranquility_constraint_has_no_condition():
    part_def = _part_def(_build(), "ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine")
    assert list(part_def.tranquility_conditions) == []


# --- Step 3: evaluating tranquility for a part instance ---

def _is_tranquil(vm: VirtualMachine, part_usage: str, **attributes) -> bool:
    """Publishes a snapshot in which `part_usage` has exactly `attributes`
    (standing in for the simulation), then asks its part def whether that
    part instance is tranquil."""
    vm.state.channel.latest_snapshot.publish({part_usage: types.SimpleNamespace(**attributes)})
    part = vm.state.sysml.lookup_table_part_instantiations.get_reference(part_usage).element_type
    return _part_def(vm, part.part_def_origin.qualified_name).is_tranquil(part, vm.state)


def test_token_depo_is_tranquil_when_no_token_at_receiver():
    vm = _build()
    assert _is_tranquil(vm, "Main::tokenDepo", receiverSens=False) is True
    assert _is_tranquil(vm, "Main::tokenDepo", receiverSens=True) is False


def test_vgr_is_tranquil_only_at_home_with_vacuum_off():
    vm = _build()
    at_home = dict(verticalEncoder=0.0, armEncoder=0.0, rotEncoder=0.0,
                   vacuumActCompressorOn=False, vacuumActValve=False)
    assert _is_tranquil(vm, "Main::vgrPickProducer", **at_home) is True
    assert _is_tranquil(vm, "Main::vgrPickProducer", **{**at_home, "armEncoder": 31.5}) is False
    assert _is_tranquil(vm, "Main::vgrPickProducer", **{**at_home, "vacuumActValve": True}) is False


def test_part_missing_from_snapshot_is_not_tranquil():
    # Startup: the simulation hasn't created the part yet (PartNotReadyError),
    # so tranquility can't be confirmed.
    vm = _build()
    vm.state.channel.latest_snapshot.publish({})
    part = vm.state.sysml.lookup_table_part_instantiations.get_reference("Main::tokenDepo").element_type
    assert _part_def(vm, part.part_def_origin.qualified_name).is_tranquil(part, vm.state) is False
