from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from hypothesis import given, strategies as st

from paperbrain.domain.enums import OrderStatus, VerificationState
from paperbrain.domain.machines import Machine
from paperbrain.domain.materials import MaterialSpec
from paperbrain.domain.orders import CustomerOrder, OrderLine
from paperbrain.domain.policies import NORMAL_POLICY
from paperbrain.domain.reels import Reel
from paperbrain.domain.snapshots import PlanningSnapshot
from paperbrain.optimization.preprocessing import ProblemPreprocessor


@given(
    reel_width=st.integers(min_value=600, max_value=2500),
    lane_width=st.integers(min_value=100, max_value=500),
    quantity=st.integers(min_value=1, max_value=500),
)
def test_generated_patterns_never_exceed_usable_width(
    reel_width: int,
    lane_width: int,
    quantity: int,
) -> None:
    material = MaterialSpec(
        family="SBS",
        grade="Property",
        compatibility_group_id=uuid4(),
        gsm_value=Decimal("250"),
    )
    machine = Machine(
        code="PROPERTY-MACHINE",
        min_web_width_mm=500,
        max_web_width_mm=2600,
        min_crosscut_length_mm=200,
        max_crosscut_length_mm=2000,
        min_lane_width_mm=100,
        max_lanes=8,
        inter_lane_kerf_mm=2,
        min_left_trim_mm=5,
        min_right_trim_mm=5,
    )
    reel = Reel(
        reel_code="PROPERTY-REEL",
        material_spec_id=material.id,
        nominal_width_mm=reel_width,
        remaining_length_mm=2_000_000,
        location_id=uuid4(),
        verification_state=VerificationState.VERIFIED,
    )
    now = datetime.now(UTC)
    order = CustomerOrder(
        customer_id=uuid4(),
        external_id="PROPERTY-ORDER",
        received_at=now,
        promised_at=now + timedelta(days=1),
        status=OrderStatus.RELEASED,
    )
    line = OrderLine(
        order_id=order.id,
        sheet_width_mm=lane_width,
        sheet_length_mm=500,
        quantity_required=quantity,
        quantity_min=quantity,
        quantity_max=quantity + 8,
        material_spec_id=material.id,
        earliest_start_at=now,
        due_at=order.promised_at,
    )
    snapshot = PlanningSnapshot(
        created_at=now,
        orders=(order,),
        order_lines=(line,),
        reels=(reel,),
        reel_segments=(reel.default_segment(),),
        machines=(machine,),
        materials=(material,),
        substitutions=(),
        policy=NORMAL_POLICY,
    )
    prepared = ProblemPreprocessor().prepare(snapshot)
    for option in prepared.options:
        pattern = option.pattern
        assert pattern.left_trim_mm + pattern.used_width_mm + pattern.right_trim_mm == pattern.usable_width_mm