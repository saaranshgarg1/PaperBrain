from decimal import Decimal
from uuid import uuid4

from paperbrain.execution.reconciliation import RunActuals, reconcile_material


def test_material_balance() -> None:
    balance = reconcile_material(
        RunActuals(
            run_id=uuid4(),
            input_mass_kg=Decimal("100"),
            good_product_mass_kg=Decimal("90"),
            retained_remainder_mass_kg=Decimal("5"),
            normal_trim_mass_kg=Decimal("3"),
            setup_mass_kg=Decimal("2"),
        )
    )
    assert balance.within_tolerance
    assert balance.variance_mass_kg == 0
