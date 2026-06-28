"""Confirmation engine (T041, US5, research R6, constitution III).

For trust-boundary actions (risk_level != none, not auto_run — and NEVER for
destructive regardless of auto_run), emit a confirmation_request activity event,
block the agent run on an asyncio.Future until the user responds, and never
auto-resolve. Pending requests persist through disconnect.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from src.models.db import db_session
from src.models.entities import (
    ActivityType,
    ConfirmationRequest,
    ConfirmationStatus,
    RiskLevel,
    Tool,
)
from src.realtime.manager import manager
from src.realtime.store import record, to_public

# session_id -> {confirmation_id: asyncio.Future}
_pending: dict[uuid.UUID, dict[uuid.UUID, asyncio.Future]] = {}


def _action_summary(name: str, arguments: dict) -> str:
    args = ", ".join(f"{k}={v}" for k, v in list(arguments.items())[:4])
    return f"{name}({args})"


async def request_confirmation(
    session_id: uuid.UUID,
    tool_id: uuid.UUID,
    tool_name: str,
    arguments: dict,
    risk_level: RiskLevel,
) -> bool:
    """Emit a confirmation_request, block until resolved. Returns True if approved."""
    summary = _action_summary(tool_name, arguments)
    with db_session() as db:
        ev = record(
            db,
            event_type=ActivityType.confirmation_request,
            payload={
                "confirmation_id": None,  # filled below
                "tool": tool_name,
                "action_summary": summary,
                "risk_level": risk_level.value,
                "arguments": arguments,
            },
            session_id=session_id,
            tool_id=tool_id,
        )
        cr = ConfirmationRequest(
            session_id=session_id,
            activity_event_id=ev.id,
            tool_id=tool_id,
            action_summary=summary,
            risk_level=risk_level,
            status=ConfirmationStatus.pending,
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        confirmation_id = cr.id
        # Backfill the confirmation_id into the event payload. Reassign the whole
        # dict (in-place JSON mutation isn't tracked without MutableDict) and
        # snapshot pub before commit (expire_on_commit would reload stale state).
        ev.payload = {**ev.payload, "confirmation_id": str(confirmation_id)}
        pub = to_public(ev)
        db.commit()
    await manager.send_event(session_id, pub)

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _pending.setdefault(session_id, {})[confirmation_id] = fut
    try:
        approved = await fut  # blocks until resolve() sets the result
    finally:
        _pending.get(session_id, {}).pop(confirmation_id, None)
    return approved


async def resolve(confirmation_id: uuid.UUID, approved: bool, user_id: uuid.UUID) -> None:
    """Resolve a pending confirmation from the WS handler. Never auto-called."""
    with db_session() as db:
        cr = db.get(ConfirmationRequest, confirmation_id)
        if cr is None or cr.status != ConfirmationStatus.pending:
            return
        cr.status = ConfirmationStatus.approved if approved else ConfirmationStatus.declined
        cr.decided_at = datetime.now(timezone.utc)
        cr.decided_by = user_id
        db.commit()
        from src.api.audit import record_decision
        record_decision(cr)
        session_id = cr.session_id
        # Emit the resolution event.
        ev = record(
            db,
            event_type=ActivityType.confirmation_result,
            payload={"confirmation_id": str(confirmation_id), "decision": "approved" if approved else "declined"},
            session_id=session_id,
        )
        pub = to_public(ev)

    # Unblock the waiting agent run.
    fut = _pending.get(session_id, {}).pop(confirmation_id, None)
    if fut is not None and not fut.done():
        fut.set_result(approved)
    await manager.send_event(session_id, pub)
