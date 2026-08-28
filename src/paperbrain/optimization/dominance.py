from __future__ import annotations

from paperbrain.domain.patterns import CuttingPattern


def remove_conservatively_dominated(
    patterns: tuple[CuttingPattern, ...],
) -> tuple[CuttingPattern, ...]:
    """Remove only patterns with identical production and strictly worse trim.

    More aggressive dominance can erase edge-position, setup, or future-flexibility
    distinctions, so the MVP deliberately keeps it conservative.
    """
    best: dict[tuple[object, ...], CuttingPattern] = {}
    for pattern in patterns:
        production = tuple(sorted((str(key), value) for key, value in pattern.production_per_crosscut.items()))
        key = (
            pattern.machine_id,
            pattern.material_spec_id,
            pattern.crosscut_length_mm,
            production,
            pattern.setup_family,
        )
        incumbent = best.get(key)
        if incumbent is None or (
            pattern.trim_total_mm + pattern.kerf_total_mm
            < incumbent.trim_total_mm + incumbent.kerf_total_mm
        ):
            best[key] = pattern
    return tuple(sorted(best.values(), key=lambda item: item.signature))
