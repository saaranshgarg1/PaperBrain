from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from paperbrain.domain.enums import PolicyName


@dataclass(frozen=True, slots=True)
class PolicyProfile:
    name: PolicyName
    version: int
    require_full_released_service: bool
    fresh_reel_penalty: int
    pattern_activation_penalty: int
    trim_area_penalty_per_million_mm2: int
    open_reel_age_credit_per_day: int
    low_confidence_length_penalty: int
    schedule_change_penalty: int
    conservative_length_quantile: Decimal
    max_patterns_per_group: int
    objective_tolerance_minor: int = 0


NORMAL_POLICY = PolicyProfile(
    name=PolicyName.NORMAL,
    version=1,
    require_full_released_service=True,
    fresh_reel_penalty=10_000,
    pattern_activation_penalty=1_000,
    trim_area_penalty_per_million_mm2=100,
    open_reel_age_credit_per_day=50,
    low_confidence_length_penalty=5_000,
    schedule_change_penalty=20_000,
    conservative_length_quantile=Decimal("0.10"),
    max_patterns_per_group=2_000,
)

POLICIES: dict[PolicyName, PolicyProfile] = {
    PolicyName.NORMAL: NORMAL_POLICY,
    PolicyName.OPEN_STOCK_CLEANUP: replace(
        NORMAL_POLICY,
        name=PolicyName.OPEN_STOCK_CLEANUP,
        fresh_reel_penalty=30_000,
        open_reel_age_credit_per_day=250,
    ),
    PolicyName.YIELD_CAMPAIGN: replace(
        NORMAL_POLICY,
        name=PolicyName.YIELD_CAMPAIGN,
        trim_area_penalty_per_million_mm2=300,
        pattern_activation_penalty=500,
    ),
    PolicyName.SERVICE_RECOVERY: replace(
        NORMAL_POLICY,
        name=PolicyName.SERVICE_RECOVERY,
        fresh_reel_penalty=1_000,
        pattern_activation_penalty=200,
    ),
    PolicyName.CASH_PRESERVATION: replace(
        NORMAL_POLICY,
        name=PolicyName.CASH_PRESERVATION,
        fresh_reel_penalty=50_000,
    ),
}


def get_policy(name: PolicyName | str) -> PolicyProfile:
    return POLICIES[PolicyName(name)]
