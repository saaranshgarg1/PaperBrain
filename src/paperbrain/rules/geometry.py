from __future__ import annotations

from dataclasses import dataclass

from paperbrain.domain.enums import EdgeLaneRestriction
from paperbrain.domain.errors import DomainViolation
from paperbrain.domain.machines import Machine
from paperbrain.domain.patterns import CuttingPattern, OrientationCandidate
from paperbrain.domain.reels import Reel, ReelSegment


@dataclass(frozen=True, slots=True)
class GeometryResult:
    valid: bool
    violations: tuple[DomainViolation, ...]


def validate_pattern_geometry(
    pattern: CuttingPattern,
    reel: Reel,
    segment: ReelSegment,
    machine: Machine,
    orientations: dict[object, OrientationCandidate],
) -> GeometryResult:
    violations: list[DomainViolation] = []
    usable = segment.usable_width_mm(reel.nominal_width_mm)

    if segment.reel_id != reel.id:
        violations.append(DomainViolation("SEGMENT_REEL_MISMATCH", "Segment belongs to another reel"))
    if not (machine.min_web_width_mm <= reel.nominal_width_mm <= machine.max_web_width_mm):
        violations.append(DomainViolation("MACHINE_WEB_LIMIT", "Reel width is outside machine limits"))
    if pattern.machine_id != machine.id:
        violations.append(DomainViolation("PATTERN_MACHINE_MISMATCH", "Pattern belongs to another machine"))
    if pattern.usable_width_mm != usable:
        violations.append(
            DomainViolation(
                "PATTERN_USABLE_WIDTH_MISMATCH",
                "Pattern usable width differs from the inspected reel segment",
            )
        )
    if len(pattern.lanes) > machine.max_lanes:
        violations.append(DomainViolation("TOO_MANY_LANES", "Pattern exceeds machine lane limit"))
    if not (
        machine.min_crosscut_length_mm
        <= pattern.crosscut_length_mm
        <= machine.max_crosscut_length_mm
    ):
        violations.append(DomainViolation("CROSSCUT_LIMIT", "Cross-cut length is outside machine limits"))
    if pattern.left_trim_mm < machine.min_left_trim_mm:
        violations.append(DomainViolation("LEFT_TRIM_TOO_SMALL", "Left trim is below machine minimum"))
    if pattern.right_trim_mm < machine.min_right_trim_mm:
        violations.append(DomainViolation("RIGHT_TRIM_TOO_SMALL", "Right trim is below machine minimum"))

    expected_kerf = machine.inter_lane_kerf_mm * max(0, len(pattern.lanes) - 1)
    if pattern.kerf_total_mm != expected_kerf:
        violations.append(DomainViolation("KERF_MISMATCH", "Pattern kerf does not match machine rule"))
    if pattern.left_trim_mm + pattern.used_width_mm + pattern.right_trim_mm != usable:
        violations.append(
            DomainViolation("PATTERN_WIDTH_BALANCE", "Trim, lanes, and kerf do not balance usable width")
        )

    previous_end = pattern.left_trim_mm
    for index, lane in enumerate(pattern.lanes):
        orientation = orientations.get(lane.orientation_id)
        expected_start = previous_end if index == 0 else previous_end + machine.inter_lane_kerf_mm
        if lane.start_mm != expected_start:
            violations.append(DomainViolation("LANE_GAP_MISMATCH", "Lane placement does not match kerf"))
        if lane.width_mm < machine.min_lane_width_mm:
            violations.append(DomainViolation("LANE_TOO_NARROW", "Lane is below machine minimum"))
        if orientation is None:
            violations.append(DomainViolation("UNKNOWN_ORIENTATION", "Lane orientation is unknown"))
        else:
            if orientation.order_line_id != lane.order_line_id:
                violations.append(DomainViolation("LANE_ORDER_MISMATCH", "Lane order does not match orientation"))
            if orientation.material_spec_id != pattern.material_spec_id:
                violations.append(
                    DomainViolation("PATTERN_MATERIAL_MISMATCH", "Pattern material differs from lane orientation")
                )
            if orientation.lane_width_mm != lane.width_mm:
                violations.append(DomainViolation("LANE_WIDTH_MISMATCH", "Lane width differs from orientation"))
            if orientation.crosscut_length_mm != pattern.crosscut_length_mm:
                violations.append(DomainViolation("MIXED_CROSSCUT_LENGTH", "Pattern mixes cross-cut lengths"))
            if machine.id not in orientation.machine_ids:
                violations.append(DomainViolation("ORIENTATION_MACHINE_MISMATCH", "Orientation is not valid on machine"))
            if not _edge_position_allowed(orientation.edge_lane_restriction, index, len(pattern.lanes)):
                violations.append(DomainViolation("EDGE_LANE_RESTRICTION", "Order is placed in a forbidden edge lane"))
        previous_end = lane.end_mm

    return GeometryResult(valid=not violations, violations=tuple(violations))


def _edge_position_allowed(restriction: EdgeLaneRestriction, index: int, lane_count: int) -> bool:
    if restriction == EdgeLaneRestriction.NONE:
        return True
    if restriction == EdgeLaneRestriction.AVOID_LEFT:
        return index != 0
    if restriction == EdgeLaneRestriction.AVOID_RIGHT:
        return index != lane_count - 1
    if restriction == EdgeLaneRestriction.INNER_ONLY:
        return lane_count >= 3 and index not in {0, lane_count - 1}
    return False