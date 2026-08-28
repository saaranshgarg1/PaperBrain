from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from paperbrain.api.container import Container
from paperbrain.domain.enums import OrderStatus, ReelState, VerificationState
from paperbrain.domain.machines import Machine
from paperbrain.domain.materials import MaterialSpec
from paperbrain.domain.orders import CustomerOrder, OrderLine
from paperbrain.domain.reels import Reel


def bootstrap(container: Container) -> None:
    compatibility_group_id = uuid4()
    material = MaterialSpec(
        family="SBS",
        grade="Demo 250 GSM",
        compatibility_group_id=compatibility_group_id,
        gsm_value=Decimal("250"),
        cost_minor_per_kg=125,
        scrap_credit_minor_per_kg=10,
        currency="USD",
    )
    container.materials.save(material)

    machine = Machine(
        code="SHEETER-01",
        min_web_width_mm=600,
        max_web_width_mm=2500,
        min_crosscut_length_mm=250,
        max_crosscut_length_mm=1800,
        min_lane_width_mm=120,
        max_lanes=6,
        inter_lane_kerf_mm=2,
        min_left_trim_mm=8,
        min_right_trim_mm=8,
        setup_loss_mm=1500,
        material_compatibility_groups=frozenset({compatibility_group_id}),
    )
    container.machines.save(machine)

    location_id = uuid4()
    open_reel = Reel(
        reel_code="DEMO-OPEN-1200",
        material_spec_id=material.id,
        nominal_width_mm=1200,
        remaining_length_mm=900_000,
        location_id=location_id,
        state=ReelState.OPENED,
        verification_state=VerificationState.VERIFIED,
        length_confidence=Decimal("0.98"),
        opened_at=datetime.now(UTC) - timedelta(days=10),
    )
    fresh_reel = Reel(
        reel_code="DEMO-FRESH-1250",
        material_spec_id=material.id,
        nominal_width_mm=1250,
        remaining_length_mm=1_500_000,
        location_id=location_id,
        verification_state=VerificationState.VERIFIED,
        length_confidence=Decimal("0.99"),
    )
    container.inventory_service.register_reel(open_reel, actor_id=None)
    container.inventory_service.register_reel(fresh_reel, actor_id=None)

    now = datetime.now(UTC)
    order = CustomerOrder(
        customer_id=uuid4(),
        external_id="DEMO-ORDER-001",
        received_at=now,
        promised_at=now + timedelta(days=2),
        status=OrderStatus.RELEASED,
    )
    lines = (
        OrderLine(
            order_id=order.id,
            sheet_width_mm=390,
            sheet_length_mm=600,
            quantity_required=900,
            quantity_min=900,
            quantity_max=918,
            material_spec_id=material.id,
            earliest_start_at=now,
            due_at=order.promised_at,
        ),
        OrderLine(
            order_id=order.id,
            sheet_width_mm=205,
            sheet_length_mm=600,
            quantity_required=600,
            quantity_min=600,
            quantity_max=612,
            material_spec_id=material.id,
            earliest_start_at=now,
            due_at=order.promised_at,
        ),
    )
    container.orders.save(order, lines)