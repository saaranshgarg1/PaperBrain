from __future__ import annotations

from typing import Protocol

from paperbrain.domain.plans import Plan
from paperbrain.optimization.preprocessing import PreparedProblem


class PlanningSolver(Protocol):
    def solve(
        self,
        problem: PreparedProblem,
        *,
        time_limit_seconds: int,
        seed: int,
    ) -> Plan: ...
