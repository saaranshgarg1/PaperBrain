from __future__ import annotations

from paperbrain.domain.enums import GrainRequirement
from paperbrain.domain.machines import Machine
from paperbrain.domain.orders import OrderLine
from paperbrain.domain.patterns import OrientationCandidate


def generate_orientations(order_line: OrderLine, machines: tuple[Machine, ...]) -> tuple[OrientationCandidate, ...]:
    result: list[OrientationCandidate] = []
    candidates = [(order_line.sheet_width_mm, order_line.sheet_length_mm, False)]
    if order_line.rotation_allowed and order_line.sheet_width_mm != order_line.sheet_length_mm:
        candidates.append((order_line.sheet_length_mm, order_line.sheet_width_mm, True))

    for lane_width, crosscut_length, rotated in candidates:
        if not _grain_allows(order_line.grain_requirement, rotated):
            continue
        compatible_machines = frozenset(
            machine.id
            for machine in machines
            if order_line.machine_allowed(machine.id)
            and machine.capabilities.supports_roll_to_sheet
            and machine.min_lane_width_mm <= lane_width <= machine.max_web_width_mm
            and machine.min_crosscut_length_mm
            <= crosscut_length
            <= machine.max_crosscut_length_mm
        )
        if compatible_machines:
            result.append(
                OrientationCandidate(
                    order_line_id=order_line.id,
                    material_spec_id=order_line.material_spec_id,
                    lane_width_mm=lane_width,
                    crosscut_length_mm=crosscut_length,
                    rotated=rotated,
                    edge_lane_restriction=order_line.edge_lane_restriction,
                    quantity_min=order_line.quantity_min,
                    quantity_max=order_line.quantity_max,
                    machine_ids=compatible_machines,
                )
            )
    return tuple(result)


def _grain_allows(requirement: GrainRequirement, rotated: bool) -> bool:
    if requirement == GrainRequirement.UNRESTRICTED:
        return True
    if requirement == GrainRequirement.MACHINE_DIRECTION:
        return not rotated
    if requirement == GrainRequirement.CROSS_DIRECTION:
        return rotated
    return False
