from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ortools.sat.python import cp_model

from paperbrain.domain.enums import OrderStatus, PlanningRunStatus
from paperbrain.domain.plans import Plan, PlanRun, PlanRunOutput, SolverMetadata
from paperbrain.optimization.objectives import ObjectiveCalculator
from paperbrain.optimization.preprocessing import PreparedProblem


class CpSatPlanner:
    def __init__(self, objective_calculator: ObjectiveCalculator | None = None) -> None:
        self._objective = objective_calculator or ObjectiveCalculator()

    def solve(
        self,
        problem: PreparedProblem,
        *,
        time_limit_seconds: int,
        seed: int,
    ) -> Plan:
        snapshot = problem.snapshot
        model = cp_model.CpModel()
        options = list(problem.options)
        status_by_order = {order.id: order.status for order in snapshot.orders}

        crosscuts: dict[int, cp_model.IntVar] = {}
        active: dict[int, cp_model.IntVar] = {}
        reel_used: dict[UUID, cp_model.IntVar] = {
            reel.id: model.new_bool_var(f"reel_used_{reel.id.hex}") for reel in snapshot.reels
        }
        for index, option in enumerate(options):
            crosscuts[index] = model.new_int_var(0, option.max_crosscuts, f"n_{index}")
            active[index] = model.new_bool_var(f"y_{index}")
            model.add(crosscuts[index] <= option.max_crosscuts * active[index])
            model.add(crosscuts[index] >= active[index])
            model.add(reel_used[option.reel_id] >= active[index])

        options_by_segment: dict[UUID, list[int]] = {}
        for index, option in enumerate(options):
            options_by_segment.setdefault(option.reel_segment_id, []).append(index)
        for segment in snapshot.reel_segments:
            indices = options_by_segment.get(segment.id, [])
            model.add(
                sum(
                    options[index].pattern.crosscut_length_mm * crosscuts[index]
                    + options[index].setup_loss_mm * active[index]
                    for index in indices
                )
                <= segment.length_mm
            )

        production: dict[UUID, cp_model.IntVar] = {}
        shortages: dict[UUID, cp_model.IntVar] = {}
        for line in snapshot.order_lines:
            production[line.id] = model.new_int_var(0, line.quantity_max, f"produced_{line.id.hex}")
            expression = sum(
                option.pattern.production_per_crosscut.get(line.id, 0) * crosscuts[index]
                for index, option in enumerate(options)
            )
            model.add(production[line.id] == expression)
            model.add(production[line.id] <= line.quantity_max)
            committed = status_by_order.get(line.order_id) in {
                OrderStatus.RELEASED,
                OrderStatus.RUNNING,
            }
            if snapshot.policy.require_full_released_service and committed:
                model.add(production[line.id] >= line.quantity_min)
                shortages[line.id] = model.new_constant(0)
            else:
                shortages[line.id] = model.new_int_var(0, line.quantity_min, f"short_{line.id.hex}")
                model.add(production[line.id] + shortages[line.id] >= line.quantity_min)
            if line.pack_size:
                remainder = model.new_int_var(0, line.pack_size - 1, f"pack_remainder_{line.id.hex}")
                model.add_modulo_equality(remainder, production[line.id], line.pack_size)
                model.add(remainder == 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(1.0, time_limit_seconds / 3)
        solver.parameters.random_seed = seed
        solver.parameters.num_search_workers = 1

        stage1 = sum(shortages.values())
        model.minimize(stage1)
        status = solver.solve(model)
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            return self._empty_plan(problem, solver, seed, PlanningRunStatus.INFEASIBLE)
        stage1_value = int(round(solver.objective_value))
        model.add(stage1 <= stage1_value)

        material_terms = []
        reels = snapshot.reel_by_id()
        materials = snapshot.material_by_id()
        for index, option in enumerate(options):
            waste_width = option.pattern.trim_total_mm + option.pattern.kerf_total_mm
            material = materials[reels[option.reel_id].material_spec_id]
            gsm_units = max(1, int(material.planning_gsm))
            cost_units = max(1, material.cost_minor_per_kg)
            trim_area_units = (
                waste_width * option.pattern.crosscut_length_mm
            ) // 1_000
            setup_area_units = (option.nominal_width_mm * option.setup_loss_mm) // 1_000
            material_terms.append(
                trim_area_units * gsm_units * cost_units * crosscuts[index]
                + setup_area_units * gsm_units * cost_units * active[index]
            )
        stage2 = sum(material_terms)
        model.minimize(stage2)
        status = solver.solve(model)
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            return self._empty_plan(problem, solver, seed, PlanningRunStatus.INFEASIBLE)
        stage2_value = int(round(solver.objective_value))
        model.add(stage2 <= stage2_value)

        fresh_terms = [
            reel_used[reel.id] * snapshot.policy.fresh_reel_penalty
            for reel in snapshot.reels
            if reel.is_fresh
        ]
        activation_terms = [
            active[index] * snapshot.policy.pattern_activation_penalty
            for index in range(len(options))
        ]
        stage3 = sum(fresh_terms + activation_terms)
        model.minimize(stage3)
        status = solver.solve(model)
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            return self._empty_plan(problem, solver, seed, PlanningRunStatus.INFEASIBLE)

        runs: list[PlanRun] = []
        sequence = 0
        for index, option in enumerate(options):
            count = solver.value(crosscuts[index])
            if count <= 0:
                continue
            outputs = tuple(
                PlanRunOutput(order_line_id=line_id, quantity=lanes * count)
                for line_id, lanes in sorted(
                    option.pattern.production_per_crosscut.items(), key=lambda item: str(item[0])
                )
            )
            runs.append(
                PlanRun(
                    reel_id=option.reel_id,
                    reel_segment_id=option.reel_segment_id,
                    machine_id=option.pattern.machine_id,
                    pattern_id=option.pattern.id,
                    crosscut_count=count,
                    consumed_length_mm=(
                        option.pattern.crosscut_length_mm * count + option.setup_loss_mm
                    ),
                    outputs=outputs,
                    sequence=sequence,
                )
            )
            sequence += 1

        option_map = {(item.reel_id, item.pattern.id): item for item in options}
        pattern_map = {item.pattern.id: item.pattern for item in options}
        objective = self._objective.calculate(
            snapshot,
            tuple(runs),
            option_map,
            pattern_map,
            snapshot.policy,
        )
        result_status = (
            PlanningRunStatus.OPTIMAL if status == cp_model.OPTIMAL else PlanningRunStatus.TIMEOUT_FEASIBLE
        )
        best_bound = Decimal(str(solver.best_objective_bound))
        objective_value = Decimal(str(solver.objective_value))
        gap = None
        if objective_value != 0:
            gap = abs(objective_value - best_bound) / abs(objective_value)
        warnings: tuple[str, ...] = ()
        if objective.service_shortage_sheets:
            warnings = (
                "The best plan leaves non-released demand incomplete; review capacity or horizon.",
            )
        return Plan(
            snapshot_id=snapshot.id,
            policy_name=snapshot.policy.name,
            runs=tuple(runs),
            objective=objective,
            status=result_status,
            solver=SolverMetadata(
                name="cpsat",
                version="runtime",
                wall_seconds=Decimal(str(solver.wall_time)),
                seed=seed,
                best_bound=best_bound,
                relative_gap=gap,
            ),
            warnings=warnings,
        )

    @staticmethod
    def _empty_plan(
        problem: PreparedProblem,
        solver: cp_model.CpSolver,
        seed: int,
        status: PlanningRunStatus,
    ) -> Plan:
        return Plan(
            snapshot_id=problem.snapshot.id,
            policy_name=problem.snapshot.policy.name,
            runs=(),
            objective=ObjectiveCalculator().calculate(
                problem.snapshot,
                (),
                {},
                {},
                problem.snapshot.policy,
            ),
            status=status,
            solver=SolverMetadata(
                name="cpsat",
                version="runtime",
                wall_seconds=Decimal(str(solver.wall_time)),
                seed=seed,
            ),
            warnings=("No feasible plan was found within the configured model and limits.",),
        )