"""Audit logging for trust-boundary decisions (T048, FR-012).

Every confirmation decision is logged with actor, target, and outcome. The
ConfirmationRequest entity already persists decided_by/decided_at/status; this
module provides a structured audit record and accessor. Constitution III.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.entities import ConfirmationRequest, ConfirmationStatus

logger = logging.getLogger("audit")


def record_decision(cr: ConfirmationRequest) -> None:
    """Log a trust-boundary decision (structured). Called on resolve()."""
    logger.info(
        "trust_boundary_decision actor=%s tool=%s risk=%s decision=%s target_session=%s",
        cr.decided_by,
        cr.tool_id,
        cr.risk_level.value,
        cr.status.value,
        cr.session_id,
    )


def list_decisions(db: Session, *, session_id: uuid.UUID | None = None) -> list[dict]:
    """Return audit entries (most recent first)."""
    stmt = select(ConfirmationRequest)
    if session_id is not None:
        stmt = stmt.where(ConfirmationRequest.session_id == session_id)
    stmt = stmt.order_by(ConfirmationRequest.decided_at.desc().nullslast())
    rows = db.execute(stmt).scalars()
    return [
        {
            "id": str(cr.id),
            "session_id": str(cr.session_id),
            "tool_id": str(cr.tool_id),
            "risk_level": cr.risk_level.value,
            "decision": cr.status.value,
            "decided_by": str(cr.decided_by) if cr.decided_by else None,
            "decided_at": cr.decided_at.isoformat() if cr.decided_at else None,
            "action_summary": cr.action_summary,
        }
        for cr in rows
        if cr.status in (ConfirmationStatus.approved, ConfirmationStatus.declined)
    ]
