from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from paperbrain.domain.enums import OrderStatus, ReelState, VerificationState
from paperbrain.domain.errors import DomainViolation
from paperbrain.domain.patterns import CuttingPattern, OrientationCandidate
from paperbrain.domain.plans import Plan
from paperbrain.domain.snapshots import PlanningSnapshot
from paperbrain.rules.compatibility import machine_material_allowed, material_allowed
from paperbrain.rules.geometry import validate_pattern_geometry


@dataclass(frozen=True, slots=True)
class PlanValidationResult:
    valid: bool
    violations: tuple[DomainViolation, ...]


class PlanValidator:
    def validate(
        self,
        plan: Plan,
        snapshot: PlanningSnapshot,
        *,
        patterns: dict[UUID, CuttingPattern],
        orientations: dict[UUID, OrientationCandidate],
    ) -> PlanValidationResult:
        violations: list[DomainViolation] = []
        reels = snapshot.reel_by_id()
        segments = snapshot.segment_by_id()
        machines = snapshot.machine_by_id()
        materials = snapshot.material_by_id()
        lines = snapshot.line_by_id()
        consumed_by_segment: dict[UUID, int] = {}

        if plan.snapshot_id != snapshot.id:
            violations.append(DomainViolation("STALE_SNAPSHOT", "Plan was built from another snapshot"))

        for run in plan.runs:
            reel = reels.get(run.reel_id)
            segment = segments.get(run.reel_segment_id)
            machine = machines.get(run.machine_id)
            pattern = patterns.get(run.pattern_id)
            if reel is None:
                violations.append(DomainViolation("UNKNOWN_REEL", "Plan references an unknown reel"))
                continue
            if segment is None:
                violations.append(DomainViolation("UNKNOWN_SEGMENT", "Plan references an unknown segment"))
                continue
            if machine is None:
                violations.append(DomainViolation("UNKNOWN_MACHINE", "Plan references an unknown machine"))
                continue
            if pattern is None:
                violations.append(DomainViolation("UNKNOWN_PATTERN", "Plan references an unknown pattern"))
                continue
            if not reel.is_executable:
                violations.append(DomainViolation("REEL_NOT_VERIFIED", "Plan uses unavailable inventory"))
            if reel.verification_state != VerificationState.VERIFIED or reel.state not in {
                ReelState.UNOPENED,
                ReelState.OPENED,
            }:
                violations.append(DomainViolation("REEL_NOT_EXECUTABLE", "Reel is not executable"))
            material = materials.get(reel.material_spec_id)
            if material is None or not machine_material_allowed(machine, material):
                violations.append(DomainViolation("MACHINE_MATERIAL_INCOMPATIBLE", "Machine cannot process reel material"))
            geometry = validate_pattern_geometry(pattern, reel, segment, machine, orientations)
            violations.extend(geometry.violations)
            expected_consumption = pattern.crosscut_length_mm * run.crosscut_count + machine.setup_loss_mm
            if run.crosscut_count <= 0 or run.consumed_length_mm != expected_consumption:
                violations.append(DomainViolation("RUN_LENGTH_MISMATCH", "Run length does not match pattern count and setup"))
            consumed_by_segment[segment.id] = consumed_by_segment.get(segment.id, 0) + run.consumed_length_mm

            expected_outputs = {
                order_line_id: lanes * run.crosscut_count
                for order_line_id, lanes in pattern.production_per_crosscut.items()
            }
            actual_outputs: dict[UUID, int] = {}
            for item in run.outputs:
                actual_outputs[item.order_line_id] = (
                    actual_outputs.get(item.order_line_id, 0) + item.quantity
                )
            if expected_outputs != actual_outputs:
                violations.append(DomainViolation("RUN_OUTPUT_MISMATCH", "Run outputs do not match pattern"))
            for order_line_id in expected_outputs:
                line = lines.get(order_line_id)
                if line is None:
                    violations.append(DomainViolation("UNKNOWN_ORDER_LINE", "Pattern references unknown order line"))
                    continue
                if not material_allowed(line, reel, snapshot.substitutions, snapshot.created_at):
                    violations.append(DomainViolation("MATERIAL_INCOMPATIBLE", "Order material is incompatible with reel"))

        for segment_id, consumed in consumed_by_segment.items():
            segment = segments[segment_id]
            if consumed > segment.length_mm:
                violations.append(DomainViolation("REEL_LENGTH_INSUFFICIENT", "Plan exceeds reel-segment length"))

        production = plan.production
        order_status = {order.id: order.status for order in snapshot.orders}
        for line in snapshot.order_lines:
            produced = production.get(line.id, 0)
            status = order_status.get(line.order_id)
            if status in {OrderStatus.RELEASED, OrderStatus.RUNNING} and produced < line.quantity_min:
                violations.append(DomainViolation("COMMITTED_SHORTAGE", "Released order is underproduced"))
            if produced > line.quantity_max:
                violations.append(DomainViolation("ORDER_TOLERANCE_VIOLATION", "Order exceeds maximum quantity"))
            if line.pack_size and produced % line.pack_size != 0:
                violations.append(DomainViolation("PACK_SIZE_VIOLATION", "Produced quantity violates pack size"))

        return PlanValidationResult(valid=not violations, violations=tuple(violations))