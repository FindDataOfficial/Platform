"""WebSocket endpoint: /ws/sessions/{id} (T012, research R5).

Handles: resume (backfill), chat (dispatch to agent loop), confirmation.
The agent loop is wired in US1 (T017/T018).
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from src.api.auth import parse_session_cookie
from src.models.db import db_session
from src.realtime.manager import backfill, manager

router = APIRouter()


def _auth_ws(websocket: WebSocket) -> uuid.UUID | None:
    cookie = websocket.cookies.get("session")
    return parse_session_cookie(cookie) if cookie else None


@router.websocket("/ws/sessions/{session_id}")
async def session_ws(
    websocket: WebSocket,
    session_id: uuid.UUID,
    resume_seq: int | None = Query(default=None, alias="last_seen_seq"),
) -> None:
    user_id = _auth_ws(websocket)
    if user_id is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    manager.connect(session_id, websocket)

    # Backfill on (re)connect: client may also send {type:resume}.
    if resume_seq:
        await backfill(websocket, session_id, resume_seq)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "resume":
                await backfill(websocket, session_id, int(msg.get("last_seen_seq", 0)))
            elif mtype == "chat":
                # Dispatch to the agent loop (US1, T018).
                from src.agent.loop import run_turn

                await run_turn(session_id, user_id, msg.get("content", ""))
            elif mtype == "confirmation":
                from src.confirm.engine import resolve

                await resolve(
                    uuid.UUID(msg["confirmation_id"]),
                    msg.get("decision") == "approve",
                    user_id,
                )
            elif mtype == "pong":
                pass
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception:
        manager.disconnect(session_id)
