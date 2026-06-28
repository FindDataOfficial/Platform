"""Activity event store: persist + replay by seq (research R5, constitution II).

Events are the single source of truth for the feed. Reconnect replays by seq.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.entities import ActivityEvent, ActivityType


def next_seq(db: Session, *, session_id: uuid.UUID | None, job_id: uuid.UUID | None) -> int:
    if session_id is not None:
        stmt = select(ActivityEvent.seq).where(ActivityEvent.session_id == session_id)
    else:
        stmt = select(ActivityEvent.seq).where(ActivityEvent.job_id == job_id)
    last = db.execute(stmt.order_by(ActivityEvent.seq.desc()).limit(1)).scalar()
    return (last or 0) + 1


def record(
    db: Session,
    *,
    event_type: ActivityType,
    payload: dict,
    session_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    tool_id: uuid.UUID | None = None,
) -> ActivityEvent:
    """Persist an activity event and return it."""
    assert (session_id is None) ^ (job_id is None), "exactly one of session_id/job_id"
    ev = ActivityEvent(
        session_id=session_id,
        job_id=job_id,
        seq=next_seq(db, session_id=session_id, job_id=job_id),
        type=event_type,
        payload=payload,
        tool_id=tool_id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def replay(
    db: Session,
    *,
    session_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    since_seq: int = 0,
) -> list[ActivityEvent]:
    if session_id is not None:
        stmt = select(ActivityEvent).where(
            ActivityEvent.session_id == session_id,
            ActivityEvent.seq > since_seq,
        )
    else:
        stmt = select(ActivityEvent).where(
            ActivityEvent.job_id == job_id,
            ActivityEvent.seq > since_seq,
        )
    return list(db.execute(stmt.order_by(ActivityEvent.seq)).scalars())


def to_public(ev: ActivityEvent) -> dict:
    return {
        "id": str(ev.id),
        "seq": ev.seq,
        "type": ev.type.value,
        "tool_id": str(ev.tool_id) if ev.tool_id else None,
        "payload": ev.payload,
        "created_at": (ev.created_at or datetime.now(timezone.utc)).isoformat(),
    }
