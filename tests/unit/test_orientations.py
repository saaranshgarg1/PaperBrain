from dataclasses import replace

from paperbrain.domain.enums import GrainRequirement
from paperbrain.rules.orientations import generate_orientations


def test_rotation_is_explicit(
    machine: object,
    order_and_line: tuple[object, object],
) -> None:
    from paperbrain.domain.machines import Machine
    from paperbrain.domain.orders import OrderLine

    assert isinstance(machine, Machine)
    _, line = order_and_line
    assert isinstance(line, OrderLine)
    assert len(generate_orientations(line, (machine,))) == 1
    rotated = replace(line, rotation_allowed=True)
    assert len(generate_orientations(rotated, (machine,))) == 2


def test_cross_direction_requires_rotation(machine: object, order_and_line: tuple[object, object]) -> None:
    from paperbrain.domain.machines import Machine
    from paperbrain.domain.orders import OrderLine

    assert isinstance(machine, Machine)
    _, line = order_and_line
    assert isinstance(line, OrderLine)
    line = replace(
        line,
        rotation_allowed=True,
        grain_requirement=GrainRequirement.CROSS_DIRECTION,
    )
    candidates = generate_orientations(line, (machine,))
    assert len(candidates) == 1
    assert candidates[0].rotated
