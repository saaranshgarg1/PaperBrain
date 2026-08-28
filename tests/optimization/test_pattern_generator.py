from paperbrain.optimization.preprocessing import ProblemPreprocessor


def test_preprocessor_generates_three_lane_pattern(snapshot: object) -> None:
    from paperbrain.domain.snapshots import PlanningSnapshot

    assert isinstance(snapshot, PlanningSnapshot)
    prepared = ProblemPreprocessor().prepare(snapshot)
    assert prepared.options
    assert any(len(option.pattern.lanes) == 3 for option in prepared.options)
    assert all(option.pattern.crosscut_length_mm == 600 for option in prepared.options)
