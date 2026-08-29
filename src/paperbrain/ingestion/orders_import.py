from __future__ import annotations

import csv
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4

from paperbrain.ingestion.issues import ImportIssue, IssueSeverity, ParsedRecord
from paperbrain.ingestion.normalization import parse_decimal, parse_gsm_and_supplier

ORDER_REQUIRED_COLUMNS = frozenset(
    {"order_number", "material", "gsm", "sheet_width_mm", "sheet_length_mm", "quantity", "due_date"}
)

YES_VALUES = frozenset({"yes", "y", "true", "1", "allowed"})
NO_VALUES = frozenset({"no", "n", "false", "0", ""})


class OrdersImportParser:
    """Parse the business-friendly customer order CSV template."""

    def parse(self, content: str) -> tuple[ParsedRecord, ...]:
        reader = csv.DictReader(StringIO(content))
        headers = frozenset(reader.fieldnames or ())
        missing = ORDER_REQUIRED_COLUMNS - headers
        if missing:
            issue = ImportIssue(
                "MISSING_COLUMNS",
                f"Required columns are missing: {', '.join(sorted(missing))}",
                IssueSeverity.ERROR,
            )
            return (ParsedRecord(0, {}, {}, (issue,)),)
        return tuple(self._parse_row(number, row) for number, row in enumerate(reader, start=2))

    def _parse_row(self, row_number: int, row: dict[str, str]) -> ParsedRecord:
        issues: list[ImportIssue] = []
        parsed: dict[str, object] = {}

        order_number = (row.get("order_number") or "").strip()
        if not order_number:
            issues.append(
                ImportIssue("MISSING_ORDER_NUMBER", "Order number is required", IssueSeverity.ERROR, "order_number")
            )
        else:
            parsed["order_number"] = order_number

        parsed["customer"] = (row.get("customer") or "").strip() or "Unknown customer"

        family = (row.get("material") or "").strip()
        if not family:
            issues.append(
                ImportIssue("MISSING_MATERIAL", "Material (family) is required", IssueSeverity.ERROR, "material")
            )
        else:
            parsed["family"] = family

        gsm, gsm_issues = parse_gsm_and_supplier(row.get("gsm"))
        parsed.update(gsm)
        issues.extend(gsm_issues)

        for column in ("sheet_width_mm", "sheet_length_mm", "quantity"):
            value = parse_decimal(row.get(column), field=column)
            if value.issue:
                issues.append(value.issue)
            elif value.value is not None and value.value <= 0:
                issues.append(
                    ImportIssue(
                        "INVALID_NUMBER",
                        f"{column} must be positive",
                        IssueSeverity.ERROR,
                        column,
                    )
                )
            else:
                parsed[column] = int(value.value or 0)

        overrun = parse_decimal(row.get("overrun_percent"), field="overrun_percent")
        if overrun.value is not None and overrun.value >= 0:
            parsed["overrun_percent"] = overrun.value

        due = self._parse_due_date(row.get("due_date"))
        if isinstance(due, ImportIssue):
            issues.append(due)
        else:
            parsed["due_at"] = due

        rotation = (row.get("rotation_allowed") or "").strip().lower()
        if rotation and rotation not in YES_VALUES | NO_VALUES:
            issues.append(
                ImportIssue(
                    "INVALID_ROTATION_FLAG",
                    "Rotation allowed must be yes or no",
                    IssueSeverity.WARNING,
                    "rotation_allowed",
                    rotation,
                )
            )
        parsed["rotation_allowed"] = rotation in YES_VALUES

        parsed["row_id"] = uuid4()
        return ParsedRecord(row_number=row_number, raw=row, parsed=parsed, issues=tuple(issues))

    def _parse_due_date(self, raw: str | None) -> datetime | ImportIssue:
        text = (raw or "").strip()
        if not text:
            return ImportIssue("MISSING_DUE_DATE", "Due date is required", IssueSeverity.ERROR, "due_date", raw)
        try:
            date_part = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return ImportIssue(
                    "INVALID_DUE_DATE",
                    "Due date must look like 2026-09-30 or a full ISO timestamp",
                    IssueSeverity.ERROR,
                    "due_date",
                    text,
                )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        return datetime.combine(date_part.date(), time(23, 59, 59), tzinfo=UTC) + timedelta(days=0)
