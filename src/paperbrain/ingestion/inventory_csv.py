from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO

from paperbrain.ingestion.issues import ImportIssue, IssueSeverity, ParsedRecord
from paperbrain.ingestion.normalization import (
    parse_decimal,
    parse_gsm_and_supplier,
    parse_identifier_tokens,
    parse_width_mm,
)


class InventoryCsvParser:
    REQUIRED_COLUMNS = frozenset({"reel_code", "width", "width_unit", "gsm", "length_mm"})

    def parse(self, content: str) -> tuple[ParsedRecord, ...]:
        reader = csv.DictReader(StringIO(content))
        headers = frozenset(reader.fieldnames or ())
        missing = self.REQUIRED_COLUMNS - headers
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

        width = parse_width_mm(row.get("width"), row.get("width_unit"))
        if width.issue:
            issues.append(width.issue)
        else:
            parsed["nominal_width_mm"] = int(width.value or 0)

        gsm, gsm_issues = parse_gsm_and_supplier(row.get("gsm"))
        parsed.update(gsm)
        issues.extend(gsm_issues)

        length = parse_decimal(row.get("length_mm"), field="length_mm")
        if length.issue:
            issues.append(length.issue)
        elif length.value is not None and length.value <= 0:
            issues.append(
                ImportIssue("INVALID_LENGTH", "Length must be positive", IssueSeverity.ERROR, "length_mm")
            )
        else:
            parsed["remaining_length_mm"] = int(length.value or 0)

        parsed["source_reel_ids"] = parse_identifier_tokens(row.get("source_reel_ids"))
        parsed["location"] = (row.get("location") or "").strip() or None
        parsed["status_text"] = (row.get("status") or "").strip() or None
        return ParsedRecord(row_number=row_number, raw=row, parsed=parsed, issues=tuple(issues))


def duplicate_reel_code_issues(records: Iterable[ParsedRecord]) -> dict[int, ImportIssue]:
    first_seen: dict[str, int] = {}
    result: dict[int, ImportIssue] = {}
    for record in records:
        code = record.parsed.get("reel_code")
        if not isinstance(code, str):
            continue
        if code in first_seen:
            result[record.row_number] = ImportIssue(
                "DUPLICATE_REEL_CODE",
                f"Reel code duplicates row {first_seen[code]}",
                IssueSeverity.ERROR,
                "reel_code",
                code,
            )
        else:
            first_seen[code] = record.row_number
    return result
