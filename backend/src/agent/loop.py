"""Agent loop (T017, US1).

Takes a chat message, calls the session's LLM via the provider layer, and emits
ActivityEvents (reasoning, llm_call with model+tokens+cost per FR-023) streamed
to the dashboard. Tools are wired in US3 (T032); confirmation in US5 (T042).
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.llm import provider as provider_mod
from src.models.db import db_session
from src.models.entities import (
    ActivityType,
    ChatSession,
    LlmModel,
    LlmProvider,
    Message,
    MessageRole,
)
from src.realtime.manager import manager
from src.realtime.store import record, to_public

logger = logging.getLogger(__name__)


def _load_model(db: Session, model_id: uuid.UUID) -> tuple[LlmModel, LlmProvider]:
    model = db.get(LlmModel, model_id)
    if model is None or not model.enabled:
        raise ValueError("model unavailable")  # edge case: disabled/removed model
    provider = db.get(LlmProvider, model.provider_id)
    if provider is None:
        raise ValueError("provider not found")
    return model, provider


def _next_message_seq(db: Session, session_id: uuid.UUID) -> int:
    last = db.execute(
        select(Message.seq).where(Message.session_id == session_id).order_by(Message.seq.desc()).limit(1)
    ).scalar()
    return (last or 0) + 1


def _tool_schemas() -> list[dict]:
    """Expose registered tool descriptors to the LLM as function schemas (T032)."""
    from src.tools.registry import all_descriptors

    return [
        {
            "name": d.name,
            "description": d.description,
            "parameters": d.input_schema,
        }
        for d in all_descriptors()
    ]


async def _invoke_tool(name: str, arguments: dict, session_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """Run a tool through the invoke path (confirmation gate applies, US5 T042)."""
    from src.tools.invoke import invoke

    res = await invoke(name, arguments, session_id=session_id, user_id=user_id)
    # Surface a compact result for the LLM; full result already streamed as event.
    if res["ok"]:
        return {"ok": True, "content": res["content"][0]["text"] if res["content"] else ""}
    return {"ok": False, "error": res["error"]}


def _history(db: Session, session_id: uuid.UUID) -> list[dict]:
    msgs = db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.seq)
    ).scalars()
    return [{"role": m.role.value, "content": m.content} for m in msgs]


def _find_alternative_model(owner_id: uuid.UUID, exclude_model_id: uuid.UUID) -> LlmModel | None:
    """FR-024: pick another enabled model owned by the user (different provider ideally)."""
    with db_session() as db:
        # models owned by the user via their providers
        from src.models.entities import LlmProvider
        prov_ids = [p.id for p in db.execute(select(LlmProvider).where(LlmProvider.owner_id == owner_id)).scalars()]
        if not prov_ids:
            return None
        alt = db.execute(
            select(LlmModel)
            .where(LlmModel.provider_id.in_(prov_ids), LlmModel.enabled, LlmModel.id != exclude_model_id)
            .order_by(LlmModel.created_at)
            .limit(1)
        ).scalar_one_or_none()
        # Detach a snapshot the caller can read outside this session.
        return alt


async def _call_with_failover(
    session: ChatSession, model: LlmModel, provider: LlmProvider, history: list[dict], session_id: uuid.UUID
) -> tuple[LlmResult | None, str]:
    """Call the LLM; on failure, fail over once to an enabled alternative (FR-024)."""
    try:
        llm = provider_mod.build_provider(provider, model)
        return await llm.complete(history), model.model_name
    except Exception as e:  # noqa: BLE001
        logger.warning("primary llm call failed: %s", e)
        alt = _find_alternative_model(session.owner_id, model.id)
        if alt is None:
            await _emit(
                session_id,
                ActivityType.error,
                {"code": "execution_error", "message": f"llm call failed: {e}"},
            )
            return None, model.model_name
        await _emit(session_id, ActivityType.reasoning, {"note": f"failing over to {alt.display_name}"})
        try:
            with db_session() as db2:
                alt_provider = db2.get(LlmProvider, alt.provider_id)
                alt_model = db2.get(LlmModel, alt.id)
                alt_name = alt_model.model_name
                llm = provider_mod.build_provider(alt_provider, alt_model)
            return await llm.complete(history), alt_name
        except Exception as e2:  # noqa: BLE001
            await _emit(
                session_id,
                ActivityType.error,
                {"code": "execution_error", "message": f"failover also failed: {e2}"},
            )
            return None, alt.model_name


async def _emit(session_id: uuid.UUID, event_type: ActivityType, payload: dict, tool_id=None) -> None:
    with db_session() as db:
        ev = record(
            db,
            event_type=event_type,
            payload=payload,
            session_id=session_id,
            tool_id=tool_id,
        )
        pub = to_public(ev)
    await manager.send_event(session_id, pub)


async def run_turn(session_id: uuid.UUID, user_id: uuid.UUID, content: str) -> None:
    """Run one chat turn: persist user message, call LLM, stream activity, persist reply."""
    with db_session() as db:
        session = db.get(ChatSession, session_id)
        if session is None or session.owner_id != user_id:
            return
        # Persist the user message.
        db.add(
            Message(
                session_id=session_id,
                role=MessageRole.user,
                content=content,
                seq=_next_message_seq(db, session_id),
            )
        )
        db.commit()
        history = _history(db, session_id)
        try:
            model, provider = _load_model(db, session.model_id)
        except ValueError as e:
            await _emit(session_id, ActivityType.error, {"code": "model_unavailable", "message": str(e)})
            return

    # Emit a reasoning event first (SC-001: first event <2s).
    await _emit(session_id, ActivityType.reasoning, {"note": "thinking"})

    # Tool-calling loop: expose descriptors, execute requested calls, repeat (T032).
    tools = _tool_schemas()
    final_text = ""
    while True:
        result, used_model_name = await _call_with_failover(session, model, provider, history, session_id)
        if result is None:
            return  # error already emitted
        usage = result.usage
        await _emit(
            session_id,
            ActivityType.llm_call,
            {
                "model": used_model_name,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "cost_usd": result.cost_usd,
            },
        )
        if not result.tool_calls:
            final_text = result.text
            break
        # Append the assistant's tool-requesting message, then execute each call.
        history.append({"role": "assistant", "content": result.text, "tool_calls": [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in result.tool_calls
        ]})
        for tc in result.tool_calls:
            await _emit(session_id, ActivityType.tool_call, {"name": tc.name, "arguments": tc.arguments})
            res = await _invoke_tool(tc.name, tc.arguments, session_id, user_id)
            await _emit(session_id, ActivityType.tool_result, res)
            history.append({"role": "tool", "name": tc.name, "content": json.dumps(res)})
        # Loop: the LLM sees the tool results and continues.

    # Persist the assistant reply.
    with db_session() as db:
        db.add(
            Message(
                session_id=session_id,
                role=MessageRole.assistant,
                content=final_text,
                seq=_next_message_seq(db, session_id),
            )
        )
        db.commit()

    await _emit(
        session_id,
        ActivityType.reasoning,
        {"note": "response", "text": final_text},
    )
