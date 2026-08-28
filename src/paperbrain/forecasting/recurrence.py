from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import median
from uuid import UUID


@dataclass(frozen=True, slots=True)
class HistoricalDemand:
    order_family_id: UUID
    occurred_at: datetime
    quantity: int


@dataclass(frozen=True, slots=True)
class RecurrenceEstimate:
    order_family_id: UUID
    recurring: bool
    median_interval_days: Decimal | None
    interval_mad_days: Decimal | None
    expected_quantity: int | None
    confidence: Decimal
    next_expected_at: datetime | None


def estimate_recurrence(history: tuple[HistoricalDemand, ...]) -> RecurrenceEstimate:
    if not history:
        raise ValueError("History cannot be empty")
    family_id = history[0].order_family_id
    if any(item.order_family_id != family_id for item in history):
        raise ValueError("History must contain one order family")
    ordered = sorted(history, key=lambda item: item.occurred_at)
    if len(ordered) < 3:
        return RecurrenceEstimate(family_id, False, None, None, None, Decimal("0"), None)

    intervals = [
        Decimal(str((right.occurred_at - left.occurred_at).total_seconds() / 86400))
        for left, right in zip(ordered, ordered[1:])
    ]
    interval = Decimal(str(median(intervals)))
    deviations = [abs(value - interval) for value in intervals]
    mad = Decimal(str(median(deviations)))
    variability = Decimal("1") if interval == 0 else min(Decimal("1"), mad / interval)
    evidence = min(Decimal("1"), Decimal(len(ordered) - 2) / Decimal("6"))
    confidence = max(Decimal("0"), evidence * (Decimal("1") - variability))
    recurring = interval > 0 and confidence >= Decimal("0.50")
    quantities = [item.quantity for item in ordered[-6:]]
    expected_quantity = int(median(quantities))
    next_at = ordered[-1].occurred_at + timedelta(days=float(interval)) if recurring else None
    return RecurrenceEstimate(
        order_family_id=family_id,
        recurring=recurring,
        median_interval_days=interval,
        interval_mad_days=mad,
        expected_quantity=expected_quantity,
        confidence=confidence,
        next_expected_at=next_at,
    )