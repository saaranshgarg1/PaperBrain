from paperbrain.optimization.preprocessing import ProblemPreprocessor
from paperbrain.optimization.solvers.cpsat import CpSatPlanner
from paperbrain.rules.feasibility import PlanValidator


def test_cpsat_plan_meets_released_demand(snapshot: object) -> None:
    from paperbrain.domain.snapshots import PlanningSnapshot

    assert isinstance(snapshot, PlanningSnapshot)
    prepared = ProblemPreprocessor().prepare(snapshot)
    plan = CpSatPlanner().solve(prepared, time_limit_seconds=10, seed=11)
    validation = PlanValidator().validate(
        plan,
        snapshot,
        patterns={option.pattern.id: option.pattern for option in prepared.options},
        orientations=prepared.orientation_map,
    )
    assert validation.valid
    assert plan.objective.service_shortage_sheets == 0
