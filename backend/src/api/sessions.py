"""Sessions HTTP API (T019, contracts/http-api.md).

List/create/get/delete chat sessions + activity replay by seq (SC-006).
Chat itself happens over the WebSocket.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import require_user
from src.models.db import get_db
from src.models.entities import ChatSession, LlmModel, Message, User
from src.realtime.store import replay, to_public

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSession(BaseModel):
    model_id: uuid.UUID
    title: str | None = None


def _owner_session(db: Session, sid: uuid.UUID, user: User) -> ChatSession:
    s = db.get(ChatSession, sid)
    if s is None or s.owner_id != user.id:
        raise HTTPException(404, "session not found")
    return s


@router.get("")
def list_sessions(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(ChatSession).where(ChatSession.owner_id == user.id).order_by(ChatSession.created_at.desc())
    ).scalars()
    return [
        {"id": str(s.id), "model_id": str(s.model_id), "title": s.title, "created_at": s.created_at.isoformat()}
        for s in rows
    ]


@router.post("")
def create_session(body: CreateSession, user: User = Depends(require_user), db: Session = Depends(get_db)):
    model = db.get(LlmModel, body.model_id)
    if model is None or not model.enabled:
        raise HTTPException(400, "model not available")
    s = ChatSession(owner_id=user.id, model_id=model.id, title=body.title)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": str(s.id), "model_id": str(s.model_id)}


@router.get("/{session_id}")
def get_session(session_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    s = _owner_session(db, session_id, user)
    msgs = db.execute(
        select(Message).where(Message.session_id == s.id).order_by(Message.seq)
    ).scalars()
    return {
        "id": str(s.id),
        "model_id": str(s.model_id),
        "title": s.title,
        "messages": [
            {"role": m.role.value, "content": m.content, "seq": m.seq} for m in msgs
        ],
    }


@router.delete("/{session_id}")
def delete_session(session_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    s = _owner_session(db, session_id, user)
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.get("/{session_id}/activity")
def get_activity(
    session_id: uuid.UUID,
    since_seq: int = Query(0),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _owner_session(db, session_id, user)
    return [to_public(ev) for ev in replay(db, session_id=session_id, since_seq=since_seq)]
