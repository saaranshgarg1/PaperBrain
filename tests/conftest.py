from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from paperbrain.domain.enums import OrderStatus, VerificationState
from paperbrain.domain.machines import Machine
from paperbrain.domain.materials import MaterialSpec
from paperbrain.domain.orders import CustomerOrder, OrderLine
from paperbrain.domain.policies import NORMAL_POLICY
from paperbrain.domain.reels import Reel
from paperbrain.domain.snapshots import PlanningSnapshot


@pytest.fixture
def material() -> MaterialSpec:
    return MaterialSpec(
        family="SBS",
        grade="Pilot",
        compatibility_group_id=uuid4(),
        gsm_value=Decimal("250"),
        cost_minor_per_kg=120,
    )


@pytest.fixture
def machine(material: MaterialSpec) -> Machine:
    return Machine(
        code="SHEETER-01",
        min_web_width_mm=500,
        max_web_width_mm=2500,
        min_crosscut_length_mm=200,
        max_crosscut_length_mm=2000,
        min_lane_width_mm=100,
        max_lanes=6,
        inter_lane_kerf_mm=2,
        min_left_trim_mm=5,
        min_right_trim_mm=5,
        setup_loss_mm=1000,
        material_compatibility_groups=frozenset({material.compatibility_group_id}),
    )


@pytest.fixture
def reel(material: MaterialSpec) -> Reel:
    return Reel(
        reel_code="R-001",
        material_spec_id=material.id,
        nominal_width_mm=1200,
        remaining_length_mm=1_000_000,
        location_id=uuid4(),
        verification_state=VerificationState.VERIFIED,
        length_confidence=Decimal("0.99"),
    )


@pytest.fixture
def order_and_line(material: MaterialSpec) -> tuple[CustomerOrder, OrderLine]:
    now = datetime.now(UTC)
    order = CustomerOrder(
        customer_id=uuid4(),
        external_id="ORDER-001",
        received_at=now,
        promised_at=now + timedelta(days=2),
        status=OrderStatus.RELEASED,
    )
    line = OrderLine(
        order_id=order.id,
        sheet_width_mm=390,
        sheet_length_mm=600,
        quantity_required=300,
        quantity_min=300,
        quantity_max=306,
        material_spec_id=material.id,
        due_at=order.promised_at,
        earliest_start_at=now,
    )
    return order, line


@pytest.fixture
def snapshot(
    material: MaterialSpec,
    machine: Machine,
    reel: Reel,
    order_and_line: tuple[CustomerOrder, OrderLine],
) -> PlanningSnapshot:
    order, line = order_and_line
    return PlanningSnapshot(
        created_at=datetime.now(UTC),
        orders=(order,),
        order_lines=(line,),
        reels=(reel,),
        reel_segments=(reel.default_segment(),),
        machines=(machine,),
        materials=(material,),
        substitutions=(),
        policy=NORMAL_POLICY,
    )
