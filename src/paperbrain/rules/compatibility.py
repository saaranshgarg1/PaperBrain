from __future__ import annotations

from datetime import datetime
from uuid import UUID

from paperbrain.domain.machines import Machine
from paperbrain.domain.materials import MaterialSpec, MaterialSubstitution
from paperbrain.domain.orders import OrderLine
from paperbrain.domain.reels import Reel


def material_allowed(
    order_line: OrderLine,
    reel: Reel,
    substitutions: tuple[MaterialSubstitution, ...],
    at: datetime,
) -> bool:
    if order_line.material_spec_id == reel.material_spec_id:
        return True
    return any(
        item.requested_material_id == order_line.material_spec_id
        and item.substitute_material_id == reel.material_spec_id
        and item.active_at(at)
        for item in substitutions
    )


def machine_material_allowed(machine: Machine, material: MaterialSpec) -> bool:
    return (
        not machine.material_compatibility_groups
        or material.compatibility_group_id in machine.material_compatibility_groups
    )


def order_machine_allowed(order_line: OrderLine, machine_id: UUID) -> bool:
    return order_line.machine_allowed(machine_id)
