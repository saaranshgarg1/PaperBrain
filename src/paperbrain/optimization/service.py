from __future__ import annotations

from dataclasses import dataclass

from paperbrain.domain.plans import Plan
from paperbrain.domain.snapshots import PlanningSnapshot
from paperbrain.optimization.heuristic import GreedyPlanner
from paperbrain.optimization.preprocessing import PreparedProblem, ProblemPreprocessor
from paperbrain.optimization.solvers.base import PlanningSolver
from paperbrain.rules.feasibility import PlanValidationResult, PlanValidator


@dataclass(frozen=True, slots=True)
class PlanningResult:
    plan: Plan
    prepared: PreparedProblem
    validation: PlanValidationResult


class PlanningService:
    def __init__(
        self,
        solver: PlanningSolver,
        preprocessor: ProblemPreprocessor | None = None,
        validator: PlanValidator | None = None,
        heuristic: GreedyPlanner | None = None,
    ) -> None:
        self._solver = solver
        self._preprocessor = preprocessor or ProblemPreprocessor()
        self._validator = validator or PlanValidator()
        self._heuristic = heuristic or GreedyPlanner()

    def solve(
        self,
        snapshot: PlanningSnapshot,
        *,
        time_limit_seconds: int,
        seed: int,
        mode: str = "full",
    ) -> PlanningResult:
        prepared = self._preprocessor.prepare(snapshot)
        plan = (
            self._heuristic.solve(prepared, seed=seed)
            if mode == "fast"
            else self._solver.solve(
                prepared,
                time_limit_seconds=time_limit_seconds,
                seed=seed,
            )
        )
        validation = self._validator.validate(
            plan,
            snapshot,
            patterns={item.pattern.id: item.pattern for item in prepared.options},
            orientations=prepared.orientation_map,
        )
        return PlanningResult(plan=plan, prepared=prepared, validation=validation)

    def validate(self, plan: Plan, prepared: PreparedProblem) -> PlanValidationResult:
        return self._validator.validate(
            plan,
            prepared.snapshot,
            patterns={item.pattern.id: item.pattern for item in prepared.options},
            orientations=prepared.orientation_map,
        )