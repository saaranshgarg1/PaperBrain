from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from paperbrain.domain.enums import EdgeLaneRestriction
from paperbrain.domain.machines import Machine
from paperbrain.domain.patterns import CuttingPattern, LanePlacement, OrientationCandidate
from paperbrain.domain.reels import Reel, ReelSegment
from paperbrain.optimization.dominance import remove_conservatively_dominated


class PatternGenerator:
    def generate(
        self,
        orientations: tuple[OrientationCandidate, ...],
        reel: Reel,
        segment: ReelSegment,
        machine: Machine,
        *,
        max_patterns: int,
    ) -> tuple[CuttingPattern, ...]:
        usable_width = segment.usable_width_mm(reel.nominal_width_mm)
        if usable_width < machine.min_left_trim_mm + machine.min_right_trim_mm + machine.min_lane_width_mm:
            return ()

        grouped: dict[tuple[UUID, int], list[OrientationCandidate]] = defaultdict(list)
        for orientation in orientations:
            if machine.id not in orientation.machine_ids:
                continue
            if orientation.lane_width_mm < machine.min_lane_width_mm:
                continue
            grouped[(orientation.material_spec_id, orientation.crosscut_length_mm)].append(orientation)

        patterns: list[CuttingPattern] = []
        for (material_spec_id, crosscut_length_mm), group in grouped.items():
            ordered = sorted(
                group,
                key=lambda item: (
                    -item.lane_width_mm,
                    str(item.order_line_id),
                    item.rotated,
                ),
            )
            self._enumerate_group(
                ordered,
                reel,
                segment,
                machine,
                usable_width,
                material_spec_id,
                crosscut_length_mm,
                patterns,
                max_patterns,
            )
            if len(patterns) >= max_patterns:
                break

        return remove_conservatively_dominated(tuple(patterns[:max_patterns]))

    def _enumerate_group(
        self,
        orientations: list[OrientationCandidate],
        reel: Reel,
        segment: ReelSegment,
        machine: Machine,
        usable_width: int,
        material_spec_id: UUID,
        crosscut_length_mm: int,
        output: list[CuttingPattern],
        max_patterns: int,
    ) -> None:
        chosen: list[OrientationCandidate] = []

        seen_signatures: set[str] = set()

        def visit(occupied_mm: int) -> None:
            if len(output) >= max_patterns:
                return
            if chosen:
                pattern = self._build_pattern(
                    chosen,
                    machine,
                    usable_width,
                    material_spec_id,
                    crosscut_length_mm,
                )
                if pattern is not None and pattern.signature not in seen_signatures:
                    output.append(pattern)
                    seen_signatures.add(pattern.signature)
            if len(chosen) >= machine.max_lanes:
                return

            for orientation in orientations:
                kerf = machine.inter_lane_kerf_mm if chosen else 0
                next_occupied = occupied_mm + kerf + orientation.lane_width_mm
                if next_occupied + machine.min_right_trim_mm > usable_width:
                    continue
                chosen.append(orientation)
                visit(next_occupied)
                chosen.pop()
                if len(output) >= max_patterns:
                    return

        visit(machine.min_left_trim_mm)

    def _build_pattern(
        self,
        chosen: list[OrientationCandidate],
        machine: Machine,
        usable_width: int,
        material_spec_id: UUID,
        crosscut_length_mm: int,
    ) -> CuttingPattern | None:
        if not self._edge_restrictions_allow(chosen):
            return None
        lanes: list[LanePlacement] = []
        cursor = machine.min_left_trim_mm
        for position, orientation in enumerate(chosen):
            if position:
                cursor += machine.inter_lane_kerf_mm
            lanes.append(
                LanePlacement(
                    orientation_id=orientation.id,
                    order_line_id=orientation.order_line_id,
                    start_mm=cursor,
                    width_mm=orientation.lane_width_mm,
                    position=position,
                )
            )
            cursor += orientation.lane_width_mm
        right_trim = usable_width - cursor
        if right_trim < machine.min_right_trim_mm:
            return None
        setup_family = "-".join(str(lane.width_mm) for lane in lanes)
        return CuttingPattern(
            machine_id=machine.id,
            material_spec_id=material_spec_id,
            crosscut_length_mm=crosscut_length_mm,
            lanes=tuple(lanes),
            usable_width_mm=usable_width,
            left_trim_mm=machine.min_left_trim_mm,
            right_trim_mm=right_trim,
            kerf_total_mm=machine.inter_lane_kerf_mm * max(0, len(lanes) - 1),
            setup_family=setup_family,
        )

    @staticmethod
    def _edge_restrictions_allow(chosen: list[OrientationCandidate]) -> bool:
        count = len(chosen)
        for index, orientation in enumerate(chosen):
            restriction = orientation.edge_lane_restriction
            if restriction == EdgeLaneRestriction.AVOID_LEFT and index == 0:
                return False
            if restriction == EdgeLaneRestriction.AVOID_RIGHT and index == count - 1:
                return False
            if restriction == EdgeLaneRestriction.INNER_ONLY and (
                count < 3 or index in {0, count - 1}
            ):
                return False
        return True