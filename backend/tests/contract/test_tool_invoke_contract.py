"""T014 — tool-invoke contract test.

Proves the uniform invoke contract: descriptor shape, schema validation,
timeout, and error codes per contracts/tool-invoke-contract.md.
Must pass after T020 (registry + invoke core).
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from src.models.entities import RiskLevel
from src.tools.invoke import ToolError, invoke
from src.tools.registry import ToolDescriptor, register, reset_registry


def _descriptor(name="echo", risk=RiskLevel.none, auto_run=False, timeout=30) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="echo back arguments",
        source_type="builtin",
        input_schema={
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
        },
        risk_level=risk,
        auto_run=auto_run,
        timeout_seconds=timeout,
    )


def test_descriptor_contract_shape():
    d = _descriptor()
    assert d.name and d.description
    assert isinstance(d.input_schema, dict)
    assert "type" in d.input_schema  # JSON Schema
    assert d.risk_level in {RiskLevel.none, RiskLevel.sensitive, RiskLevel.destructive}


def test_valid_input_returns_structured_result():
    reset_registry()

    async def echo(args):
        return {"echoed": args["msg"]}

    register(_descriptor(), echo)
    res = asyncio.run(invoke("echo", {"msg": "hi"}))
    assert res["ok"] is True
    assert res["content"][0]["text"] == json.dumps({"echoed": "hi"})
    assert res["error"] is None


def test_invalid_input_returns_error_code():
    reset_registry()

    async def echo(args):
        return {"echoed": args["msg"]}

    register(_descriptor(), echo)
    res = asyncio.run(invoke("echo", {}))  # missing required msg
    assert res["ok"] is False
    assert res["error"]["code"] == "invalid_input"


def test_timeout_returns_timeout_code():
    reset_registry()

    async def slow(args):
        await asyncio.sleep(5)
        return {}

    register(_descriptor(name="slow", timeout=0), slow)  # 0s timeout
    res = asyncio.run(invoke("slow", {"msg": "x"}))
    assert res["ok"] is False
    assert res["error"]["code"] == "timeout"


def test_not_found_returns_error_code():
    reset_registry()
    res = asyncio.run(invoke("does_not_exist", {}))
    assert res["ok"] is False
    assert res["error"]["code"] == "not_found"


def test_execution_error_returns_error_code():
    reset_registry()

    async def boom(args):
        raise RuntimeError("kaboom")

    register(_descriptor(name="boom"), boom)
    res = asyncio.run(invoke("boom", {"msg": "x"}))
    assert res["ok"] is False
    assert res["error"]["code"] == "execution_error"


def test_destructive_never_auto_run():
    """FR-011: a destructive descriptor cannot be auto_run."""
    from src.tools.registry import register as _reg

    reset_registry()
    d = _descriptor(risk=RiskLevel.destructive, auto_run=True)
    with pytest.raises(ToolError):
        _reg(d, lambda args: None)
