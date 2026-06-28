"""Tool invoke core (T020, contracts/tool-invoke-contract.md).

Validates args against input_schema, enforces timeout, returns a structured
result {ok, content, error} with error codes. Confirmation gating (FR-010/011)
is added in US5 via confirm/ — this module is the base invoke path.
"""

from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from contextvars import ContextVar

import jsonschema

from src.models.entities import RiskLevel
from src.tools.registry import ToolError, get

# Set by the agent loop before invoking a tool so executors (browser/computer)
# can access the session without changing the executor signature.
current_session_id: ContextVar[uuid.UUID | None] = ContextVar("current_session_id", default=None)


def _validate(args: dict, schema: dict) -> None:
    try:
        jsonschema.validate(args, schema)
    except jsonschema.ValidationError as e:
        raise ToolError("invalid_input", f"argument validation failed: {e.message}")


def _ok(content: object) -> dict:
    return {
        "ok": True,
        "content": [{"type": "text", "text": json.dumps(content, default=str)}],
        "error": None,
    }


def _err(code: str, message: str) -> dict:
    return {"ok": False, "content": [], "error": {"code": code, "message": message}}


async def invoke(
    name: str,
    arguments: dict,
    *,
    timeout: int | None = None,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> dict:
    entry = get(name)
    if entry is None:
        return _err("not_found", f"tool not registered: {name}")
    descriptor, executor = entry
    try:
        _validate(arguments, descriptor.input_schema)
    except ToolError as e:
        return _err(e.code, e.message)

    # Confirmation gate (FR-010/FR-011, research R6): trust-boundary tools require
    # explicit approval. Destructive tools NEVER auto-run regardless of auto_run.
    needs_confirm = descriptor.risk_level != RiskLevel.none and not descriptor.auto_run
    if descriptor.risk_level == RiskLevel.destructive:
        needs_confirm = True  # FR-011
    if needs_confirm and session_id is not None:
        from src.confirm.engine import request_confirmation

        approved = await request_confirmation(
            session_id=session_id,
            tool_id=descriptor.tool_id or uuid.uuid4(),
            tool_name=descriptor.name,
            arguments=arguments,
            risk_level=descriptor.risk_level,
        )
        if not approved:
            return _err("declined", "user declined the action")

    limit = timeout if timeout is not None else descriptor.timeout_seconds
    tok = current_session_id.set(session_id)
    try:
        result = await asyncio.wait_for(executor(arguments), timeout=limit or 0.0001)
        return _ok(result)
    except asyncio.TimeoutError:
        return _err("timeout", f"tool exceeded {limit}s")
    except ToolError as e:
        return _err(e.code, e.message)
    except Exception as e:  # noqa: BLE001 — contract: surface execution errors
        traceback.print_exc()
        return _err("execution_error", str(e))
    finally:
        current_session_id.reset(tok)


if __name__ == "__main__":
    # ponytail self-check: the contract holds for a trivial builtin.
    from src.tools.registry import ToolDescriptor, register, reset_registry
    from src.models.entities import RiskLevel

    reset_registry()

    async def echo(a):
        return a

    register(
        ToolDescriptor(
            name="echo",
            description="echo",
            source_type="builtin",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
            risk_level=RiskLevel.none,
        ),
        echo,
    )
    r = asyncio.run(invoke("echo", {"msg": "hi"}))
    assert r["ok"] and r["content"][0]["text"] == '{"msg": "hi"}', r
    assert asyncio.run(invoke("echo", {}))["error"]["code"] == "invalid_input"
    assert asyncio.run(invoke("nope", {}))["error"]["code"] == "not_found"
    print("invoke contract self-check OK")
