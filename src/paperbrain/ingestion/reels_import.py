from __future__ import annotations

import csv
from decimal import Decimal
from io import StringIO
from uuid import uuid4

from paperbrain.ingestion.issues import ImportIssue, IssueSeverity, ParsedRecord
from paperbrain.ingestion.normalization import (
    parse_decimal,
    parse_gsm_and_supplier,
    parse_width_mm,
)

REEL_REQUIRED_COLUMNS = frozenset(
    {"reel_code", "material", "gsm", "width", "width_unit", "length_mm"}
)

OPEN_STATES = frozenset({"open", "opened", "in use", "partial", "partially used"})
NEW_STATES = frozenset({"new", "unopened", "fresh", "sealed", ""})


class ReelsImportParser:
    """Parse the business-friendly reel inventory CSV template."""

    def parse(self, content: str) -> tuple[ParsedRecord, ...]:
        reader = csv.DictReader(StringIO(content))
        headers = frozenset(reader.fieldnames or ())
        missing = REEL_REQUIRED_COLUMNS - headers
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

        reel_code = (row.get("reel_code") or "").strip()
        if not reel_code:
            issues.append(
                ImportIssue("MISSING_REEL_CODE", "Reel code is required", IssueSeverity.ERROR, "reel_code")
            )
        else:
            parsed["reel_code"] = reel_code

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

        width = parse_width_mm(row.get("width"), row.get("width_unit"))
        if width.issue:
            issues.append(width.issue)
        else:
            parsed["nominal_width_mm"] = int(width.value or 0)

        length_mm = parse_decimal(row.get("length_mm"), field="length_mm")
        if length_mm.issue:
            issues.append(length_mm.issue)
        elif length_mm.value is not None and length_mm.value <= 0:
            issues.append(
                ImportIssue("INVALID_LENGTH", "Length must be positive", IssueSeverity.ERROR, "length_mm")
            )
        else:
            parsed["remaining_length_mm"] = int(length_mm.value or 0)

        mass = parse_decimal(row.get("mass_kg"), field="mass_kg")
        if mass.value is not None and mass.value > 0:
            parsed["net_mass_kg"] = mass.value

        cost = parse_decimal(row.get("cost_per_kg"), field="cost_per_kg")
        if cost.value is not None and cost.value > 0:
            parsed["cost_minor_per_kg"] = int((cost.value * 100).quantize(Decimal("1")))

        currency = (row.get("currency") or "").strip().upper()
        if currency and len(currency) != 3:
            issues.append(
                ImportIssue(
                    "INVALID_CURRENCY",
                    "Currency must be a 3-letter code such as USD or INR; defaulting to USD",
                    IssueSeverity.WARNING,
                    "currency",
                    currency,
                )
            )
        elif currency:
            parsed["currency"] = currency

        status = (row.get("status") or "").strip().lower()
        if status and status not in OPEN_STATES | NEW_STATES:
            issues.append(
                ImportIssue(
                    "UNKNOWN_STATUS",
                    "Status not recognized; leave empty for a new sealed reel or use 'open'",
                    IssueSeverity.WARNING,
                    "status",
                    status,
                )
            )
        parsed["is_open"] = status in OPEN_STATES

        parsed["grade"] = (row.get("grade") or "").strip() or None
        parsed["location"] = (row.get("location") or "").strip() or None
        parsed["row_id"] = uuid4()
        return ParsedRecord(row_number=row_number, raw=row, parsed=parsed, issues=tuple(issues))
