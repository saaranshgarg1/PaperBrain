from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from paperbrain.domain.patterns import CuttingPattern, OrientationCandidate, PatternOption
from paperbrain.domain.snapshots import PlanningSnapshot
from paperbrain.optimization.pattern_generator import PatternGenerator
from paperbrain.rules.compatibility import machine_material_allowed, material_allowed
from paperbrain.rules.orientations import generate_orientations


@dataclass(frozen=True, slots=True)
class PreparedProblem:
    snapshot: PlanningSnapshot
    orientations: tuple[OrientationCandidate, ...]
    options: tuple[PatternOption, ...]

    @property
    def orientation_map(self) -> dict[UUID, OrientationCandidate]:
        return {item.id: item for item in self.orientations}

    @property
    def pattern_map(self) -> dict[UUID, CuttingPattern]:
        return {item.pattern.id: item.pattern for item in self.options}


class ProblemPreprocessor:
    def __init__(self, pattern_generator: PatternGenerator | None = None) -> None:
        self._generator = pattern_generator or PatternGenerator()

    def prepare(self, snapshot: PlanningSnapshot) -> PreparedProblem:
        orientations = tuple(
            orientation
            for line in snapshot.order_lines
            for orientation in generate_orientations(line, snapshot.machines)
        )
        materials = snapshot.material_by_id()
        orientations_by_machine: dict[UUID, list[OrientationCandidate]] = {
            machine.id: [] for machine in snapshot.machines
        }
        for orientation in orientations:
            for machine_id in orientation.machine_ids:
                orientations_by_machine.setdefault(machine_id, []).append(orientation)

        options: list[PatternOption] = []
        reels = snapshot.reel_by_id()
        for segment in snapshot.reel_segments:
            reel = reels[segment.reel_id]
            reel_material = materials.get(reel.material_spec_id)
            if reel_material is None:
                continue
            for machine in snapshot.machines:
                if not machine_material_allowed(machine, reel_material):
                    continue
                eligible = tuple(
                    orientation
                    for orientation in orientations_by_machine.get(machine.id, ())
                    if material_allowed(
                        snapshot.line_by_id()[orientation.order_line_id],
                        reel,
                        snapshot.substitutions,
                        snapshot.created_at,
                    )
                )
                patterns = self._generator.generate(
                    eligible,
                    reel,
                    segment,
                    machine,
                    max_patterns=snapshot.policy.max_patterns_per_group,
                )
                for pattern in patterns:
                    options.append(
                        PatternOption(
                            reel_id=reel.id,
                            reel_segment_id=segment.id,
                            pattern=pattern,
                            available_length_mm=segment.length_mm,
                            nominal_width_mm=reel.nominal_width_mm,
                            is_fresh_reel=reel.is_fresh,
                            setup_loss_mm=machine.setup_loss_mm,
                        )
                    )
        return PreparedProblem(snapshot=snapshot, orientations=orientations, options=tuple(options))