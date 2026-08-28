from __future__ import annotations

from decimal import Decimal
from math import ceil
from uuid import UUID

from paperbrain.domain.enums import PlanningRunStatus
from paperbrain.domain.patterns import PatternOption
from paperbrain.domain.plans import Plan, PlanRun, PlanRunOutput, SolverMetadata
from paperbrain.optimization.objectives import ObjectiveCalculator
from paperbrain.optimization.preprocessing import PreparedProblem


class GreedyPlanner:
    """Deterministic, validated warm-start and emergency planning heuristic."""

    def __init__(self, objective_calculator: ObjectiveCalculator | None = None) -> None:
        self._objective = objective_calculator or ObjectiveCalculator()

    def solve(self, problem: PreparedProblem, *, seed: int = 0) -> Plan:
        snapshot = problem.snapshot
        demand = {line.id: line.quantity_min for line in snapshot.order_lines}
        maxima = {line.id: line.quantity_max for line in snapshot.order_lines}
        produced = {line.id: 0 for line in snapshot.order_lines}
        remaining_length = {
            segment.id: segment.length_mm for segment in snapshot.reel_segments
        }
        activated_on_segment: set[tuple[UUID, UUID]] = set()
        runs: list[PlanRun] = []

        ordered_options = sorted(problem.options, key=lambda option: self._score(option, demand))
        sequence = 0
        made_progress = True
        while made_progress and any(produced[line_id] < quantity for line_id, quantity in demand.items()):
            made_progress = False
            best_choice: tuple[PatternOption, int] | None = None
            best_score: tuple[int, int, int, str] | None = None

            for option in ordered_options:
                counts = option.pattern.production_per_crosscut
                activation = (option.reel_segment_id, option.pattern.id)
                if activation in activated_on_segment:
                    continue
                if not any(produced.get(line_id, 0) < demand.get(line_id, 0) for line_id in counts):
                    continue
                setup = option.setup_loss_mm
                available = remaining_length[option.reel_segment_id] - setup
                max_by_length = max(0, available // option.pattern.crosscut_length_mm)
                if max_by_length <= 0:
                    continue

                useful_needed = max(
                    ceil(max(0, demand.get(line_id, 0) - produced.get(line_id, 0)) / lane_count)
                    for line_id, lane_count in counts.items()
                )
                max_by_tolerance = min(
                    (maxima.get(line_id, 0) - produced.get(line_id, 0)) // lane_count
                    for line_id, lane_count in counts.items()
                )
                crosscuts = min(max_by_length, useful_needed, max_by_tolerance)
                if crosscuts <= 0:
                    continue

                helpful = sum(
                    min(
                        max(0, demand.get(line_id, 0) - produced.get(line_id, 0)),
                        lane_count * crosscuts,
                    )
                    for line_id, lane_count in counts.items()
                )
                waste_width = option.pattern.trim_total_mm + option.pattern.kerf_total_mm
                score = (
                    -helpful,
                    1 if option.is_fresh_reel else 0,
                    waste_width,
                    option.pattern.signature,
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best_choice = (option, crosscuts)

            if best_choice is None:
                break
            option, crosscuts = best_choice
            activation = (option.reel_segment_id, option.pattern.id)
            setup = option.setup_loss_mm
            consumed = setup + option.pattern.crosscut_length_mm * crosscuts
            remaining_length[option.reel_segment_id] -= consumed
            activated_on_segment.add(activation)
            outputs = tuple(
                PlanRunOutput(order_line_id=line_id, quantity=lane_count * crosscuts)
                for line_id, lane_count in sorted(
                    option.pattern.production_per_crosscut.items(), key=lambda item: str(item[0])
                )
            )
            for item in outputs:
                produced[item.order_line_id] += item.quantity
            runs.append(
                PlanRun(
                    reel_id=option.reel_id,
                    reel_segment_id=option.reel_segment_id,
                    machine_id=option.pattern.machine_id,
                    pattern_id=option.pattern.id,
                    crosscut_count=crosscuts,
                    consumed_length_mm=consumed,
                    outputs=outputs,
                    sequence=sequence,
                )
            )
            sequence += 1
            made_progress = True

        option_map = {(item.reel_id, item.pattern.id): item for item in problem.options}
        pattern_map = {item.pattern.id: item.pattern for item in problem.options}
        objective = self._objective.calculate(
            snapshot,
            tuple(runs),
            option_map,
            pattern_map,
            snapshot.policy,
        )
        status = (
            PlanningRunStatus.FEASIBLE
            if objective.service_shortage_sheets == 0
            else PlanningRunStatus.INFEASIBLE
        )
        return Plan(
            snapshot_id=snapshot.id,
            policy_name=snapshot.policy.name,
            runs=tuple(runs),
            objective=objective,
            status=status,
            solver=SolverMetadata(
                name="greedy",
                version="1",
                wall_seconds=Decimal("0"),
                seed=seed,
            ),
            warnings=("Heuristic plan; no optimality claim.",),
        )

    @staticmethod
    def _score(option: PatternOption, demand: dict[UUID, int]) -> tuple[int, int, int, str]:
        covered = sum(
            demand.get(line_id, 0) * lanes
            for line_id, lanes in option.pattern.production_per_crosscut.items()
        )
        return (
            1 if option.is_fresh_reel else 0,
            option.pattern.trim_total_mm + option.pattern.kerf_total_mm,
            -covered,
            option.pattern.signature,
        )