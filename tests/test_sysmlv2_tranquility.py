"""Step 1 of the tranquility work (Language-Safe-and-Execution-Tranquility-points.md,
Topic 8): the interpreter recognises constraints labelled `#Tranquility`
(LiveModeling::Tranquility) in complete-interesting-simulation.

Written ahead of the implementation. `syntax._is_tranquility_constraint` is
looked up on the module inside the test, not imported at the top, so that
until it exists that test fails on its own rather than the whole module
failing to collect.
"""

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
