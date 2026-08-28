from paperbrain.optimization.heuristic import GreedyPlanner
from paperbrain.optimization.preprocessing import ProblemPreprocessor
from paperbrain.rules.feasibility import PlanValidator


def test_greedy_plan_is_independently_validated(snapshot: object) -> None:
    from paperbrain.domain.snapshots import PlanningSnapshot

    assert isinstance(snapshot, PlanningSnapshot)
    prepared = ProblemPreprocessor().prepare(snapshot)
    plan = GreedyPlanner().solve(prepared, seed=7)
    validation = PlanValidator().validate(
        plan,
        snapshot,
        patterns={option.pattern.id: option.pattern for option in prepared.options},
        orientations=prepared.orientation_map,
    )
    assert validation.valid
    assert plan.objective.service_shortage_sheets == 0
