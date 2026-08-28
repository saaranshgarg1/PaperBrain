from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from paperbrain.persistence.inventory_repositories import (
    SqlEventStore,
    SqlReelRepository,
    SqlReelSegmentRepository,
)


class SqlInventoryUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self.reels: SqlReelRepository
        self.segments: SqlReelSegmentRepository
        self.events: SqlEventStore

    def __enter__(self) -> SqlInventoryUnitOfWork:
        self.session = self._session_factory()
        self.reels = SqlReelRepository(self.session)
        self.segments = SqlReelSegmentRepository(self.session)
        self.events = SqlEventStore(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self.session is not None
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()
        self.session = None
