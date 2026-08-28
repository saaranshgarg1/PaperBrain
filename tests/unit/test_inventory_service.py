from uuid import uuid4

from paperbrain.application.in_memory import (
    InMemoryEventStore,
    InMemoryReelRepository,
    InMemoryReelSegmentRepository,
)
from paperbrain.application.inventory_service import InventoryService
from paperbrain.domain.enums import ReelState, VerificationState
from paperbrain.domain.reels import Reel


def test_register_verify_and_reserve_reel(reel: Reel) -> None:
    reels = InMemoryReelRepository()
    segments = InMemoryReelSegmentRepository()
    events = InMemoryEventStore()
    service = InventoryService(reels, segments, events)

    provisional = Reel(
        reel_code=reel.reel_code,
        material_spec_id=reel.material_spec_id,
        nominal_width_mm=reel.nominal_width_mm,
        remaining_length_mm=reel.remaining_length_mm,
        location_id=reel.location_id,
        verification_state=VerificationState.PROVISIONAL,
    )
    registered = service.register_reel(provisional, actor_id=None)
    assert registered.version == 1
    assert len(events.for_aggregate(registered.id)) == 1

    verified = service.verify_reel(registered.id, actor_id=None)
    assert verified.verification_state == VerificationState.VERIFIED
    assert verified.version == 2

    reservation_id = uuid4()
    reserved = service.reserve(verified.id, reservation_id, actor_id=None)
    assert reserved.state == ReelState.RESERVED
    assert reserved.reservation_id == reservation_id
    assert len(events.for_aggregate(registered.id)) == 3
