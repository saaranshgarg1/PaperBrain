from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from paperbrain.domain.materials import MaterialSpec
from paperbrain.domain.patterns import CuttingPattern, PatternOption
from paperbrain.domain.plans import ObjectiveBreakdown, PlanRun
from paperbrain.domain.policies import PolicyProfile
from paperbrain.domain.snapshots import PlanningSnapshot


def area_mm2_to_mass_kg(area_mm2: int, gsm: Decimal) -> Decimal:
    return Decimal(area_mm2) * gsm / Decimal("1000000000")


def mass_cost_minor(mass_kg: Decimal, material: MaterialSpec) -> int:
    return int(
        (mass_kg * Decimal(material.cost_minor_per_kg)).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )


class ObjectiveCalculator:
    def calculate(
        self,
        snapshot: PlanningSnapshot,
        runs: tuple[PlanRun, ...],
        options: dict[tuple[UUID, UUID], PatternOption],
        patterns: dict[UUID, CuttingPattern],
        policy: PolicyProfile,
    ) -> ObjectiveBreakdown:
        materials = snapshot.material_by_id()
        lines = snapshot.line_by_id()
        reels = snapshot.reel_by_id()
        production: dict[UUID, int] = {}
        trim_area = 0
        material_loss_minor = 0
        activated_reels: set[UUID] = set()
        activated_patterns = 0

        for run in runs:
            pattern = patterns[run.pattern_id]
            option = options[(run.reel_id, run.pattern_id)]
            reel = reels[run.reel_id]
            material = materials[reel.material_spec_id]
            waste_width = pattern.trim_total_mm + pattern.kerf_total_mm
            run_trim_area = waste_width * pattern.crosscut_length_mm * run.crosscut_count
            setup_area = option.nominal_width_mm * option.setup_loss_mm
            loss_area = run_trim_area + setup_area
            trim_area += loss_area
            material_loss_minor += mass_cost_minor(
                area_mm2_to_mass_kg(loss_area, material.planning_gsm), material
            )
            activated_patterns += 1
            activated_reels.add(run.reel_id)
            for item in run.outputs:
                production[item.order_line_id] = production.get(item.order_line_id, 0) + item.quantity

        shortages = sum(
            max(0, line.quantity_min - production.get(line.id, 0)) for line in lines.values()
        )
        fresh_reels = sum(1 for reel_id in activated_reels if reels[reel_id].is_fresh)
        return ObjectiveBreakdown(
            service_shortage_sheets=shortages,
            material_loss_minor=material_loss_minor,
            trim_area_mm2=trim_area,
            fresh_reels_opened=fresh_reels,
            patterns_activated=activated_patterns,
        )