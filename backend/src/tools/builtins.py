"""Builtin tools (US3) — a minimal set so the agent can act without external deps.

Registered behind the same tool contract (constitution I). Add real builtins as
needed; these are the trivial ones the dashboard can demonstrate.
"""

from __future__ import annotations

import datetime as _dt

from src.models.entities import RiskLevel
from src.tools.registry import ToolDescriptor, register


async def _echo(args: dict) -> dict:
    return {"echoed": args.get("msg", "")}


async def _now(args: dict) -> dict:
    tz = args.get("timezone", "UTC")
    return {"now": _dt.datetime.now(_dt.timezone.utc).isoformat(), "timezone": tz}


def register_builtins() -> None:
    register(
        ToolDescriptor(
            name="echo",
            description="Echo back a message.",
            source_type="builtin",
            input_schema={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
            risk_level=RiskLevel.none,
        ),
        _echo,
    )
    register(
        ToolDescriptor(
            name="current_time",
            description="Get the current UTC time, optionally for a named timezone.",
            source_type="builtin",
            input_schema={
                "type": "object",
                "properties": {"timezone": {"type": "string"}},
            },
            risk_level=RiskLevel.none,
        ),
        _now,
    )
