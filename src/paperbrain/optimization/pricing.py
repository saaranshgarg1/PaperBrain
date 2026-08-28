from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from paperbrain.domain.patterns import OrientationCandidate


@dataclass(frozen=True, slots=True)
class PricingItem:
    orientation: OrientationCandidate
    dual_value: Decimal
    max_count: int


@dataclass(frozen=True, slots=True)
class PricingResult:
    counts: dict[UUID, int]
    used_width_mm: int
    dual_value: Decimal
    reduced_cost: Decimal


class BoundedKnapsackPricer:
    """Integer dynamic-programming pricing subproblem for one width/cut-length group."""

    def price(
        self,
        items: tuple[PricingItem, ...],
        *,
        usable_width_mm: int,
        left_trim_mm: int,
        right_trim_mm: int,
        inter_lane_kerf_mm: int,
        max_lanes: int,
        base_pattern_cost: Decimal,
    ) -> PricingResult | None:
        capacity = usable_width_mm - left_trim_mm - right_trim_mm
        if capacity <= 0 or max_lanes <= 0:
            return None

        # State value is (dual value, counts). Width includes kerf before every
        # lane, then one kerf is refunded from non-empty terminal states.
        states: dict[tuple[int, int], tuple[Decimal, dict[UUID, int]]] = {
            (0, 0): (Decimal("0"), {})
        }
        for item in items:
            next_states = dict(states)
            lane_width = item.orientation.lane_width_mm + inter_lane_kerf_mm
            for (width, lanes), (value, counts) in states.items():
                for count in range(1, item.max_count + 1):
                    new_lanes = lanes + count
                    new_width = width + lane_width * count
                    if new_lanes > max_lanes:
                        break
                    effective_width = new_width - inter_lane_kerf_mm
                    if effective_width > capacity:
                        break
                    candidate_value = value + item.dual_value * count
                    key = (new_width, new_lanes)
                    incumbent = next_states.get(key)
                    if incumbent is None or candidate_value > incumbent[0]:
                        candidate_counts = dict(counts)
                        candidate_counts[item.orientation.id] = count
                        next_states[key] = (candidate_value, candidate_counts)
            states = next_states

        best: PricingResult | None = None
        for (width_with_extra_kerf, lanes), (dual_value, counts) in states.items():
            if lanes == 0:
                continue
            used_width = width_with_extra_kerf - inter_lane_kerf_mm
            reduced_cost = base_pattern_cost - dual_value
            candidate = PricingResult(counts, used_width, dual_value, reduced_cost)
            if best is None or candidate.reduced_cost < best.reduced_cost:
                best = candidate
        return best
