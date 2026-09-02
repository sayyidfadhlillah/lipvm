import pygame

from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts.vacuum_gripper import (
    VacuumGripperMachine, VGR_BASE_LENGTH, VGR_BASE_WIDTH, VGR_TOWER_BASE_LENGTH, VGR_TOWER_BASE_WIDTH,
    DEFAULT_ARM_PIPE_LENGTH, DEFAULT_ARM_PIPE_WIDTH, MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE, MAX_ARM_ENCODER_VALUE,
    MAX_ROT_ENCODER_VALUE, VGR_TOKEN_GRIPPER_LENGTH, VGR_TOKEN_GRIPPER_WIDTH, ARM_EXTENSION_PIPE_WIDTH,
)
from languages.sysmlv2.simulation_models.fischertechnik.fischertechnik_parts_visualization.generic import MachineVisualization
from languages.sysmlv2.simulation_models.fischertechnik import factory_visualization as fv
from languages.sysmlv2.simulation_models.fischertechnik.factory_visualization import _to_screen, TOKEN_OUTLINE_COLOR
from languages.sysmlv2.simulation_models.fischertechnik.movement_computation_model import arm_encoder_to_model_size, rot_encoder_to_degrees

# Farthest the arm can ever reach from center (fixed pipe + full extension)
# -- drives how big the local composite surface needs to be. Square, not
# just wide: the arm's *drawing* is always along local +x before rotation,
# but rotEncoder (VacuumGripperMachine) can point the whole arm in any
# direction once rotated onto the composite -- a surface only tall enough
# for the base/tower (as it used to be, back when the arm never rotated
# independently) would clip the tip off-canvas the moment the arm swings
# toward vertical (e.g. 90/270 degrees), even though the horizontal resting
# angles look fine. Same "rotate the whole composite, then center-blit"
# trick ConveyorBeltVisualization uses to stay valid (pygame.transform.rotate
# preserves a surface's own center across rotation -- true regardless of
# what's drawn inside it, but only useful here because the origin (machine
# center) sits exactly at that surface center, which requires the surface
# to be symmetric around it).
VGR_MAX_REACH = DEFAULT_ARM_PIPE_LENGTH + MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE

# VGR_SURFACE_WIDTH/HEIGHT used to live here as a module-level constant
# baked from SCALE at import time; moved into draw() below since SCALE can
# now change mid-session on a window resize
# (FischertechnikVisualization.run()'s VIDEORESIZE handling) and this
# needs to track it.

VGR_BASE_COLOR = (90, 90, 100)         # the foot -- base metal plate
VGR_TOWER_COLOR = (55, 55, 65)         # the mast the arm pivots around/reaches out from
VGR_ARM_PIPE_COLOR = (120, 120, 130)   # fixed pipe, center to DEFAULT_ARM_PIPE_LENGTH -- doesn't itself extend

# VGR_ARM_PIPE_WIDTH used to live here as a fixed 6px constant, unrelated to
# SCALE -- moved into draw() below (same DEFAULT_ARM_PIPE_WIDTH * SCALE
# pattern CB_SENSOR_WIDTH already established for the conveyor belt's own
# sensor bands) now that DEFAULT_ARM_PIPE_WIDTH is a real model-unit
# measurement (fischertechnik_parts/vacuum_gripper.py), not an arbitrary
# rendering choice. MIN_VGR_ARM_PIPE_WIDTH_PX floors it at 1px --
# pygame.draw.line() needs width >= 1 to draw anything at all.
MIN_VGR_ARM_PIPE_WIDTH_PX = 1
VGR_ARM_ROD_COLOR = (150, 150, 160)    # extendable segment, past the fixed pipe -- driven live by armEncoder

# VGR_ARM_ROD_WIDTH used to live here as a fixed 4px constant, unrelated to
# SCALE -- moved into draw() below (same ARM_EXTENSION_PIPE_WIDTH * SCALE
# pattern DEFAULT_ARM_PIPE_WIDTH already established for the fixed pipe)
# now that ARM_EXTENSION_PIPE_WIDTH is a real model-unit measurement
# (fischertechnik_parts/vacuum_gripper.py), not an arbitrary rendering
# choice. MIN_VGR_ARM_ROD_WIDTH_PX floors it at 1px, same
# pygame.draw.line() reasoning as MIN_VGR_ARM_PIPE_WIDTH_PX.
MIN_VGR_ARM_ROD_WIDTH_PX = 1
VGR_GRIPPER_COLOR = (255, 195, 20)     # suction head, at the end of the (currently zero-length) extendable segment -- brighter/more saturated than before so it pops against the base plate's cool greys even at 1px clearance from its edge
VGR_GRIPPER_OUTLINE_COLOR = TOKEN_OUTLINE_COLOR  # outline around the suction head -- it sits mostly past the base plate's own edge, over the viewport's white BACKGROUND_COLOR/light GRID_LINE_COLOR, so it needs the same dark outline factory_visualization.py already uses to keep a light-colored shape visible against that background (a white ring would vanish there)

# The suction head used to be drawn as a plain circle (VGR_GRIPPER_RADIUS,
# now removed); replaced with the actual rectangular footprint of the real
# part (fischertechnik_parts/vacuum_gripper.py's VGR_TOKEN_GRIPPER_LENGTH/
# WIDTH, real measurements -- 2.2cm/4cm -- not arbitrary rendering choices,
# same CB_SENSOR_WIDTH/DEFAULT_ARM_PIPE_WIDTH treatment). LENGTH runs along
# local +x (the arm's own reach axis, same convention DEFAULT_ARM_PIPE_LENGTH/
# DEFAULT_ARM_PIPE_WIDTH already use), WIDTH perpendicular to it.
# MIN_VGR_TOKEN_GRIPPER_SIZE_PX floors each side at 1px so the rect stays
# visible/renderable at very low SCALE. Outline width is a fraction of the
# rect's own smaller side rather than a fixed pixel amount -- same
# TOKEN_OUTLINE_WIDTH_RATIO reasoning factory_visualization.py's
# _draw_token() uses, so the ring doesn't dominate the shape at small SCALE.
MIN_VGR_TOKEN_GRIPPER_SIZE_PX = 1
VGR_TOKEN_GRIPPER_OUTLINE_WIDTH_RATIO = 0.15
MIN_VGR_TOKEN_GRIPPER_OUTLINE_WIDTH_PX = 1


class VacuumGripperVisualization(MachineVisualization):
    """Draws a VacuumGripperMachine as seen from directly above, in three
    parts: a base (the foot -- a metal plate at ground level), a tower
    (the mast rising from the base, which the arm pivots around and
    reaches out from -- a vertical column collapses to a rectangle/circle
    in a top-down view, since it doesn't itself rotate or extend), and an
    arm reaching out from the tower.

    The arm itself has two segments: a fixed pipe from center to
    DEFAULT_ARM_PIPE_LENGTH (structural housing, never moves), and an
    extendable rod beyond that whose length tracks armEncoder live, via
    arm_encoder_to_model_size() (movement_computation_model.py). The whole
    arm also swivels around the tower live, tracking rotEncoder via
    rot_encoder_to_degrees() -- a separate rotation stage from the
    machine's own placement (base/tower position, whole-composite
    rotation via placementCoordinate.degrees), since the arm's swivel is
    independent of where the machine itself sits/faces in the factory.

    No panel_input_fields()/panel_buttons() override -- both fall back
    to MachineVisualization's own "nothing" defaults. There used to be a
    "Target" (horizontal/rot) input row feeding "Pick"/"Place"/"Safe Pos"
    buttons that called pick()/place()/moveToSafePosition() directly;
    removed once they stopped being useful enough to keep around -- this
    machine's own behavior is already driven entirely by the SysML
    model's own `do`/`accept` behavior (vgr-cb-true-simulation.xmi's
    VGRMissionWith2CB), proven working end-to-end, so a manual panel
    control duplicating that isn't needed to exercise this machine kind
    anymore.
    """

    machine_type = VacuumGripperMachine
    panel_label = "Gripper"

    def panel_lines(self, machine: VacuumGripperMachine) -> list[str]:
        return [
            f"currentCommand: {machine.currentCommand}",
            f"executionStatus: {machine.executionStatus}",
            f"verticalEncoder: {machine.verticalEncoder}",
            f"armEncoder: {machine.armEncoder}",
            f"rotEncoder: {machine.rotEncoder}",
            f"vacuumActValve: {machine.vacuumActValve}",
            f"vacuumActCompressorOn: {machine.vacuumActCompressorOn}",
        ]

    def draw(self, screen: pygame.Surface, machine: VacuumGripperMachine) -> None:
        SCALE = fv.SCALE
        VGR_SURFACE_WIDTH = int(2 * VGR_MAX_REACH * SCALE) + 20
        VGR_SURFACE_HEIGHT = VGR_SURFACE_WIDTH

        surface = pygame.Surface((VGR_SURFACE_WIDTH, VGR_SURFACE_HEIGHT), pygame.SRCALPHA)
        center = surface.get_rect().center

        base_rect = pygame.Rect(0, 0, int(VGR_BASE_LENGTH * SCALE), int(VGR_BASE_WIDTH * SCALE))
        base_rect.center = center
        pygame.draw.rect(surface, VGR_BASE_COLOR, base_rect, border_radius=4)

        tower_rect = pygame.Rect(0, 0, int(VGR_TOWER_BASE_LENGTH * SCALE), int(VGR_TOWER_BASE_WIDTH * SCALE))
        tower_rect.center = center
        pygame.draw.rect(surface, VGR_TOWER_COLOR, tower_rect, border_radius=2)

        # Arm (pipe + rod + gripper tip) drawn on its own same-size surface
        # along local +x, then rotated around its own center by the live
        # rotEncoder angle before being blitted onto the base/tower
        # composite -- kept as a separate rotation stage from the
        # whole-machine one below (placementCoordinate.degrees, this
        # VacuumGripperMachine's fixed orientation in the factory), since
        # the arm swivels around the tower independently of that. Using
        # the same VGR_SURFACE_WIDTH/HEIGHT for arm_surface as the main
        # composite is what makes centering the rotated result trivial:
        # both surfaces share the same center point, so blitting at
        # `center` lines them up regardless of the rotation angle (same
        # "rotate the whole composite, then center-blit" trick used below,
        # applied one level deeper).
        arm_surface = pygame.Surface((VGR_SURFACE_WIDTH, VGR_SURFACE_HEIGHT), pygame.SRCALPHA)
        arm_center = arm_surface.get_rect().center

        pipe_width = max(MIN_VGR_ARM_PIPE_WIDTH_PX, round(DEFAULT_ARM_PIPE_WIDTH * SCALE))
        pipe_end = (arm_center[0] + DEFAULT_ARM_PIPE_LENGTH * SCALE, arm_center[1])
        pygame.draw.line(arm_surface, VGR_ARM_PIPE_COLOR, arm_center, pipe_end, width=pipe_width)

        extension = arm_encoder_to_model_size(machine.armEncoder, MAX_ARM_ENCODER_VALUE, MAX_ARM_EXTENSION_LENGTH_MODEL_SIZE)
        tip_end = (pipe_end[0] + extension * SCALE, arm_center[1])
        rod_width = max(MIN_VGR_ARM_ROD_WIDTH_PX, round(ARM_EXTENSION_PIPE_WIDTH * SCALE))
        pygame.draw.line(arm_surface, VGR_ARM_ROD_COLOR, pipe_end, tip_end, width=rod_width)

        gripper_px_length = max(MIN_VGR_TOKEN_GRIPPER_SIZE_PX, round(VGR_TOKEN_GRIPPER_LENGTH * SCALE))
        gripper_px_width = max(MIN_VGR_TOKEN_GRIPPER_SIZE_PX, round(VGR_TOKEN_GRIPPER_WIDTH * SCALE))
        gripper_outline_width = max(
            MIN_VGR_TOKEN_GRIPPER_OUTLINE_WIDTH_PX,
            round(min(gripper_px_length, gripper_px_width) * VGR_TOKEN_GRIPPER_OUTLINE_WIDTH_RATIO))
        gripper_rect = pygame.Rect(0, 0, gripper_px_length, gripper_px_width)
        gripper_rect.center = tip_end
        pygame.draw.rect(arm_surface, VGR_GRIPPER_COLOR, gripper_rect, border_radius=2)
        pygame.draw.rect(arm_surface, VGR_GRIPPER_OUTLINE_COLOR, gripper_rect, width=gripper_outline_width, border_radius=2)

        arm_rotation_degrees = rot_encoder_to_degrees(machine.rotEncoder, MAX_ROT_ENCODER_VALUE)
        rotated_arm = pygame.transform.rotate(arm_surface, arm_rotation_degrees)
        surface.blit(rotated_arm, rotated_arm.get_rect(center=center))

        rotated = pygame.transform.rotate(surface, machine.placementCoordinate.degrees)
        px, py = _to_screen(machine.placementCoordinate)
        screen.blit(rotated, rotated.get_rect(center=(px, py)))
