from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from paperbrain.api.container import Container
from paperbrain.domain.enums import OrderStatus, ReelState
from paperbrain.domain.materials import MaterialSpec
from paperbrain.domain.orders import CustomerOrder, OrderLine
from paperbrain.domain.reels import Reel
from paperbrain.ingestion.issues import ImportIssue, IssueSeverity, ParsedRecord

DEFAULT_LOCATION = "Imported Stock"
DEFAULT_OVERRUN_PERCENT = Decimal("2")


@dataclass(frozen=True, slots=True)
class ImportRowIssue:
    row: int
    code: str
    message: str
    severity: str
    field: str | None = None
    raw_value: Any = None
    suggestion: Any = None


@dataclass(frozen=True, slots=True)
class ImportResult:
    kind: str
    dry_run: bool
    created_reels: int = 0
    created_materials: int = 0
    created_orders: int = 0
    created_order_lines: int = 0
    skipped_rows: int = 0
    materials_to_create: tuple[str, ...] = ()
    issues: tuple[ImportRowIssue, ...] = ()
    row_count: int = 0


def _material_key(family: str, gsm: Decimal | None) -> tuple[str, str]:
    gsm_text = "range" if gsm is None else str(gsm.normalize())
    return (family.strip().lower(), gsm_text)


def _find_material(container: Container, family: str, gsm: Decimal | None) -> MaterialSpec | None:
    key = _material_key(family, gsm)
    for material in container.materials.list_all():
        if _material_key(material.family, material.gsm_value) == key:
            return material
    return None


def import_reels(
    container: Container, records: tuple[ParsedRecord, ...], *, dry_run: bool
) -> ImportResult:
    issues: list[ImportRowIssue] = []
    existing_codes = {reel.reel_code for reel in container.reels.list_all()}
    seen_codes: dict[str, int] = {}
    new_material_labels: list[str] = []
    new_material_keys: set[tuple[str, str]] = set()
    created_reels = 0
    created_materials = 0
    family_groups: dict[str, UUID] = {}
    for material in container.materials.list_all():
        family_groups.setdefault(material.family.strip().lower(), material.compatibility_group_id)

    for record in records:
        row_issues = list(record.issues)
        parsed = record.parsed
        code = parsed.get("reel_code")
        if isinstance(code, str):
            if code in existing_codes:
                row_issues.append(
                    ImportIssue(
                        "DUPLICATE_REEL_CODE",
                        f"Reel code {code!r} already exists in the system",
                        IssueSeverity.ERROR,
                        "reel_code",
                        code,
                    )
                )
            elif code in seen_codes:
                row_issues.append(
                    ImportIssue(
                        "DUPLICATE_REEL_CODE",
                        f"Reel code duplicates row {seen_codes[code]}",
                        IssueSeverity.ERROR,
                        "reel_code",
                        code,
                    )
                )
            else:
                seen_codes[code] = record.row_number

        if any(issue.severity == IssueSeverity.ERROR for issue in row_issues):
            issues.extend(_row_issues(record.row_number, row_issues))
            continue

        family = str(parsed["family"])
        gsm = parsed.get("gsm_value")
        gsm_decimal = Decimal(str(gsm)) if gsm is not None else None
        material = _find_material(container, family, gsm_decimal)
        if material is None:
            key = _material_key(family, gsm_decimal)
            if key not in new_material_keys:
                new_material_keys.add(key)
                new_material_labels.append(f"{family} {gsm_decimal or ''} GSM".strip())
            if dry_run:
                issues.extend(_row_issues(record.row_number, row_issues))
                continue

            group = family_groups.get(family.strip().lower(), uuid4())
            grade = parsed.get("grade") or f"{family} {gsm_decimal} GSM"
            material = MaterialSpec(
                family=family,
                grade=str(grade),
                compatibility_group_id=group,
                gsm_value=gsm_decimal,
                gsm_min=parsed.get("gsm_min") if gsm_decimal is None else None,
                gsm_max=parsed.get("gsm_max") if gsm_decimal is None else None,
                cost_minor_per_kg=int(parsed.get("cost_minor_per_kg", 0) or 0),
                currency=str(parsed.get("currency") or "USD"),
            )
            container.materials.save(material)
            family_groups[family.strip().lower()] = group
            created_materials += 1
        elif dry_run:
            issues.extend(_row_issues(record.row_number, row_issues))
            continue

        location_name = parsed.get("location") or DEFAULT_LOCATION
        location_id = container.locations.setdefault(str(location_name), uuid4())

        state = ReelState.OPENED if parsed.get("is_open") else ReelState.UNOPENED
        mass = parsed.get("net_mass_kg")
        reel = Reel(
            reel_code=str(parsed["reel_code"]),
            material_spec_id=material.id,
            nominal_width_mm=int(parsed["nominal_width_mm"]),
            remaining_length_mm=int(parsed["remaining_length_mm"]),
            location_id=location_id,
            state=state,
            net_mass_kg=Decimal(str(mass)) if mass is not None else None,
            length_confidence=Decimal("0.5"),
            opened_at=datetime.now(UTC) if state == ReelState.OPENED else None,
        )
        container.inventory_service.register_reel(reel, actor_id=None)
        existing_codes.add(reel.reel_code)
        created_reels += 1
        issues.extend(_row_issues(record.row_number, row_issues))

    return ImportResult(
        kind="reels",
        dry_run=dry_run,
        created_reels=created_reels,
        created_materials=created_materials,
        skipped_rows=_count_skipped(issues),
        materials_to_create=tuple(new_material_labels),
        issues=tuple(issues),
        row_count=len(records),
    )


def import_orders(
    container: Container, records: tuple[ParsedRecord, ...], *, dry_run: bool
) -> ImportResult:
    issues: list[ImportRowIssue] = []
    existing_order_numbers = {order.external_id for order in container.orders.list_all()}
    created_orders = 0
    created_lines = 0
    skipped = 0

    rows_by_order: dict[str, list[ParsedRecord]] = {}
    for record in records:
        if any(issue.severity == IssueSeverity.ERROR for issue in record.issues):
            skipped += 1
            issues.extend(_row_issues(record.row_number, record.issues))
            continue
        order_number = str(record.parsed["order_number"])
        if order_number in existing_order_numbers:
            skipped += 1
            issues.extend(
                _row_issues(
                    record.row_number,
                    (
                        ImportIssue(
                            "DUPLICATE_ORDER_NUMBER",
                            f"Order number {order_number!r} already exists",
                            IssueSeverity.ERROR,
                            "order_number",
                            order_number,
                        ),
                    ),
                )
            )
            continue
        rows_by_order.setdefault(order_number, []).append(record)

    now = datetime.now(UTC)
    for order_number, rows in rows_by_order.items():
        pending_lines: list[OrderLine] = []
        order_issues: list[tuple[int, list[ImportIssue]]] = []
        fatal = False
        for record in rows:
            row_issues = list(record.issues)
            parsed = record.parsed
            gsm = parsed.get("gsm_value")
            gsm_decimal = Decimal(str(gsm)) if gsm is not None else None
            material = _find_material(container, str(parsed["family"]), gsm_decimal)
            if material is None:
                row_issues.append(
                    ImportIssue(
                        "MATERIAL_NOT_FOUND",
                        "No material in the system matches this family and GSM; "
                        "import the matching reels or create the material first",
                        IssueSeverity.ERROR,
                        "material",
                        f"{parsed['family']} {parsed.get('gsm', '')}",
                    )
                )
                fatal = True
            if any(issue.severity == IssueSeverity.ERROR for issue in row_issues):
                fatal = True
                order_issues.append((record.row_number, row_issues))
                continue

            due_at = parsed["due_at"]
            assert isinstance(due_at, datetime)
            overrun = parsed.get("overrun_percent", DEFAULT_OVERRUN_PERCENT)
            quantity_required = int(parsed["quantity"])
            quantity_max = quantity_required + int(
                (Decimal(quantity_required) * Decimal(str(overrun)) / Decimal("100")).to_integral_value()
            )
            pending_lines.append(
                OrderLine(
                    order_id=uuid4(),
                    sheet_width_mm=int(parsed["sheet_width_mm"]),
                    sheet_length_mm=int(parsed["sheet_length_mm"]),
                    quantity_required=quantity_required,
                    quantity_min=quantity_required,
                    quantity_max=max(quantity_max, quantity_required),
                    material_spec_id=material.id if material else uuid4(),
                    due_at=due_at,
                    earliest_start_at=min(now, due_at),
                    rotation_allowed=bool(parsed["rotation_allowed"]),
                )
            )
            order_issues.append((record.row_number, row_issues))

        if fatal or not pending_lines:
            skipped += len(rows)
            for row_number, row_issues in order_issues:
                issues.extend(_row_issues(row_number, row_issues))
            continue

        if dry_run:
            for row_number, row_issues in order_issues:
                issues.extend(_row_issues(row_number, row_issues))
            continue

        customer_name = str(rows[0].parsed["customer"])
        customer_id = container.customers.setdefault(customer_name, uuid4())
        promised_at = max(line.due_at for line in pending_lines)
        order = CustomerOrder(
            customer_id=customer_id,
            external_id=order_number,
            received_at=now,
            promised_at=promised_at,
            status=OrderStatus.CONFIRMED,
        )
        final_lines = tuple(
            OrderLine(
                order_id=order.id,
                sheet_width_mm=line.sheet_width_mm,
                sheet_length_mm=line.sheet_length_mm,
                quantity_required=line.quantity_required,
                quantity_min=line.quantity_min,
                quantity_max=line.quantity_max,
                material_spec_id=line.material_spec_id,
                due_at=line.due_at,
                earliest_start_at=line.earliest_start_at,
                rotation_allowed=line.rotation_allowed,
            )
            for line in pending_lines
        )
        container.orders.save(order, final_lines)
        created_orders += 1
        created_lines += len(final_lines)
        existing_order_numbers.add(order_number)
        for row_number, row_issues in order_issues:
            issues.extend(_row_issues(row_number, row_issues))

    return ImportResult(
        kind="orders",
        dry_run=dry_run,
        created_orders=created_orders,
        created_order_lines=created_lines,
        skipped_rows=skipped,
        issues=tuple(issues),
        row_count=len(records),
    )


def _count_skipped(issues: list[ImportRowIssue]) -> int:
    error_rows = {issue.row for issue in issues if issue.severity == "error"}
    return len(error_rows)


def _row_issues(row_number: int, issues: tuple[ImportIssue, ...]) -> list[ImportRowIssue]:
    return [
        ImportRowIssue(
            row=row_number,
            code=issue.code,
            message=issue.message,
            severity=issue.severity.value,
            field=issue.field,
            raw_value=issue.raw_value,
            suggestion=issue.suggestion,
        )
        for issue in issues
    ]
