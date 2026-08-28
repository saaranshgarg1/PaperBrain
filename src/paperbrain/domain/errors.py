from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DomainViolation:
    code: str
    message: str
    field: str | None = None
    context: dict[str, Any] | None = None


class DomainError(ValueError):
    def __init__(self, violation: DomainViolation) -> None:
        self.violation = violation
        super().__init__(violation.message)


class ConcurrencyError(RuntimeError):
    pass


class NotFoundError(LookupError):
    pass
