from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from paperbrain.domain.patterns import CuttingPattern


@dataclass(frozen=True, slots=True)
class RestrictedMasterResult:
    objective: Decimal
    demand_duals: dict[UUID, Decimal]
    pattern_usage: dict[UUID, Decimal]


class RestrictedMaster(Protocol):
    def solve(self, patterns: tuple[CuttingPattern, ...]) -> RestrictedMasterResult: ...


class PatternPricingOracle(Protocol):
    def improving_patterns(
        self,
        demand_duals: dict[UUID, Decimal],
        existing_signatures: frozenset[str],
    ) -> tuple[CuttingPattern, ...]: ...


@dataclass(frozen=True, slots=True)
class ColumnGenerationResult:
    master: RestrictedMasterResult
    patterns: tuple[CuttingPattern, ...]
    iterations: int
    converged: bool


class ColumnGenerationLoop:
    def __init__(self, master: RestrictedMaster, pricing: PatternPricingOracle) -> None:
        self._master = master
        self._pricing = pricing

    def solve(
        self,
        initial_patterns: tuple[CuttingPattern, ...],
        *,
        max_iterations: int = 100,
    ) -> ColumnGenerationResult:
        patterns = list(initial_patterns)
        final = self._master.solve(tuple(patterns))
        for iteration in range(1, max_iterations + 1):
            signatures = frozenset(pattern.signature for pattern in patterns)
            additions = self._pricing.improving_patterns(final.demand_duals, signatures)
            additions = tuple(item for item in additions if item.signature not in signatures)
            if not additions:
                return ColumnGenerationResult(final, tuple(patterns), iteration, True)
            patterns.extend(additions)
            final = self._master.solve(tuple(patterns))
        return ColumnGenerationResult(final, tuple(patterns), max_iterations, False)
