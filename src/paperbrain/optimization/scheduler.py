from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from paperbrain.domain.patterns import CuttingPattern
from paperbrain.domain.plans import PlanRun


def sequence_runs(
    runs: tuple[PlanRun, ...],
    patterns: dict[UUID, CuttingPattern],
    *,
    frozen_run_ids: frozenset[UUID] = frozenset(),
) -> tuple[PlanRun, ...]:
    frozen = sorted(
        (run for run in runs if run.id in frozen_run_ids),
        key=lambda run: run.sequence,
    )
    flexible = sorted(
        (run for run in runs if run.id not in frozen_run_ids),
        key=lambda run: (
            str(run.machine_id),
            str(patterns[run.pattern_id].material_spec_id),
            patterns[run.pattern_id].setup_family,
            str(run.reel_id),
        ),
    )
    return tuple(
        replace(run, sequence=index) for index, run in enumerate([*frozen, *flexible])
    )
