from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from paperbrain.ingestion.issues import ImportIssue, IssueSeverity

MM_PER_INCH = Decimal("25.4")


@dataclass(frozen=True, slots=True)
class ParsedNumber:
    value: Decimal | None
    issue: ImportIssue | None = None


def parse_decimal(raw: str | None, *, field: str) -> ParsedNumber:
    text = (raw or "").strip().replace(",", "")
    if not text:
        return ParsedNumber(
            None,
            ImportIssue("MISSING_VALUE", f"{field} is missing", IssueSeverity.ERROR, field, raw),
        )
    try:
        return ParsedNumber(Decimal(text))
    except InvalidOperation:
        return ParsedNumber(
            None,
            ImportIssue("INVALID_NUMBER", f"{field} is not numeric", IssueSeverity.ERROR, field, raw),
        )


def parse_width_mm(raw: str | None, unit: str | None) -> ParsedNumber:
    parsed = parse_decimal(raw, field="width")
    if parsed.value is None:
        return parsed
    normalized_unit = (unit or "").strip().lower()
    if normalized_unit in {"mm", "millimetre", "millimetres", "millimeter", "millimeters"}:
        value = parsed.value
    elif normalized_unit in {"in", "inch", "inches", '"'}:
        value = parsed.value * MM_PER_INCH
    else:
        suggestion = "in" if parsed.value < Decimal("100") else "mm"
        return ParsedNumber(
            None,
            ImportIssue(
                "UNIT_AMBIGUOUS",
                "Width unit is missing or unsupported",
                IssueSeverity.ERROR,
                "width",
                raw,
                suggestion,
            ),
        )
    if value <= 0:
        return ParsedNumber(
            None,
            ImportIssue("INVALID_WIDTH", "Width must be positive", IssueSeverity.ERROR, "width", raw),
        )
    return ParsedNumber(value.quantize(Decimal("1")))


def parse_gsm_and_supplier(raw: str | None) -> tuple[dict[str, object], tuple[ImportIssue, ...]]:
    text = (raw or "").strip()
    if not text:
        return {}, (
            ImportIssue("MISSING_GSM", "GSM is missing", IssueSeverity.ERROR, "gsm", raw),
        )
    range_match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*", text)
    if range_match:
        low = Decimal(range_match.group(1))
        high = Decimal(range_match.group(2))
        if low <= 0 or high < low:
            return {}, (
                ImportIssue("INVALID_GSM_RANGE", "GSM range is invalid", IssueSeverity.ERROR, "gsm", raw),
            )
        return {"gsm_min": low, "gsm_max": high}, (
            ImportIssue(
                "GSM_RANGE_REQUIRES_REVIEW",
                "GSM is a range and cannot be treated as an exact executable value",
                IssueSeverity.WARNING,
                "gsm",
                raw,
            ),
        )

    number_match = re.match(r"\s*(\d+(?:\.\d+)?)", text)
    if not number_match:
        return {}, (
            ImportIssue("INVALID_GSM", "GSM does not begin with a numeric value", IssueSeverity.ERROR, "gsm", raw),
        )
    gsm = Decimal(number_match.group(1))
    supplier = text[number_match.end() :].strip(" ()-/") or None
    result: dict[str, object] = {"gsm_value": gsm}
    if supplier:
        result["supplier_grade"] = supplier
    return result, ()


def parse_identifier_tokens(raw: str | None) -> tuple[str, ...]:
    text = (raw or "").strip()
    if not text:
        return ()
    return tuple(token for token in re.split(r"[,;/\s]+", text) if token)
