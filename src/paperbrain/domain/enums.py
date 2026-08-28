from __future__ import annotations

from enum import StrEnum


class VerificationState(StrEnum):
    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    QUARANTINED = "quarantined"
    RETIRED = "retired"


class ReelState(StrEnum):
    UNOPENED = "unopened"
    OPENED = "opened"
    RESERVED = "reserved"
    STAGED = "staged"
    RUNNING = "running"
    QUARANTINED = "quarantined"
    EXHAUSTED = "exhausted"
    SPLIT = "split"
    MISSING = "missing"
    SCRAPPED = "scrapped"


class QualityStatus(StrEnum):
    RELEASED = "released"
    HOLD = "hold"
    DOWNGRADED = "downgraded"
    REJECTED = "rejected"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    VALIDATION_REQUIRED = "validation_required"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    RUNNING = "running"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class GrainRequirement(StrEnum):
    UNRESTRICTED = "unrestricted"
    MACHINE_DIRECTION = "machine_direction"
    CROSS_DIRECTION = "cross_direction"


class EdgeLaneRestriction(StrEnum):
    NONE = "none"
    AVOID_LEFT = "avoid_left"
    AVOID_RIGHT = "avoid_right"
    INNER_ONLY = "inner_only"


class PlanningRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    FEASIBLE = "feasible"
    OPTIMAL = "optimal"
    TIMEOUT_FEASIBLE = "timeout_feasible"
    INFEASIBLE = "infeasible"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MeasurementMethod(StrEnum):
    SCALE = "scale"
    MANUAL = "manual"
    SENSOR = "sensor"
    MACHINE_COUNTER = "machine_counter"
    DERIVED = "derived"


class PolicyName(StrEnum):
    NORMAL = "normal"
    OPEN_STOCK_CLEANUP = "open_stock_cleanup"
    YIELD_CAMPAIGN = "yield_campaign"
    SERVICE_RECOVERY = "service_recovery"
    CASH_PRESERVATION = "cash_preservation"


class EventType(StrEnum):
    REEL_RECEIVED = "ReelReceived"
    REEL_MEASURED = "ReelMeasured"
    REEL_INSPECTED = "ReelInspected"
    REEL_MOVED = "ReelMoved"
    REEL_RESERVED = "ReelReserved"
    RESERVATION_RELEASED = "ReservationReleased"
    REEL_STAGED = "ReelStaged"
    RUN_STARTED = "RunStarted"
    RUN_PAUSED = "RunPaused"
    RUN_COMPLETED = "RunCompleted"
    RUN_ABORTED = "RunAborted"
    REEL_OPENED = "ReelOpened"
    REEL_SPLIT = "ReelSplit"
    CHILD_REEL_CREATED = "ChildReelCreated"
    REEL_EXHAUSTED = "ReelExhausted"
    FINISHED_GOODS_CREATED = "FinishedGoodsCreated"
    WASTE_RECORDED = "WasteRecorded"
    REMAINDER_RETURNED = "RemainderReturned"
    REEL_QUARANTINED = "ReelQuarantined"
    REEL_RELEASED_FROM_HOLD = "ReelReleasedFromHold"
    REEL_MISSING = "ReelMissing"
    REEL_SCRAPPED = "ReelScrapped"
