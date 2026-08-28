from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from paperbrain.persistence.models import OutboxRow


def enqueue(session: Session, topic: str, payload: dict[str, Any]) -> OutboxRow:
    row = OutboxRow(id=uuid4(), topic=topic, payload=payload)
    session.add(row)
    return row
