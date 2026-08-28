from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ImportIssue:
    code: str
    message: str
    severity: IssueSeverity
    field: str | None = None
    raw_value: Any = None
    suggestion: Any = None


@dataclass(frozen=True, slots=True)
class ParsedRecord:
    row_number: int
    raw: dict[str, str]
    parsed: dict[str, Any]
    issues: tuple[ImportIssue, ...] = field(default_factory=tuple)

    @property
    def executable(self) -> bool:
        return not any(issue.severity == IssueSeverity.ERROR for issue in self.issues)
