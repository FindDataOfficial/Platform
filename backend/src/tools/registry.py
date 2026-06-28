"""Tool registry: uniform tool descriptors + executors (T020, constitution I).

Every capability (MCP, skill, builtin, browser, computer) registers here behind
one contract. Validation + timeout live in invoke.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from src.models.entities import RiskLevel, ToolSourceType


@dataclass
class ToolDescriptor:
    name: str
    description: str
    source_type: str  # ToolSourceType value
    input_schema: dict
    risk_level: RiskLevel = RiskLevel.none
    auto_run: bool = False
    timeout_seconds: int = 30
    tool_id: uuid.UUID | None = None
    _executor: Callable[[dict], Awaitable[object]] | None = field(default=None, repr=False)


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# name -> (descriptor, executor)
_REGISTRY: dict[str, tuple[ToolDescriptor, Callable[[dict], Awaitable[object]]]] = {}


def register(descriptor: ToolDescriptor, executor: Callable[[dict], Awaitable[object]]) -> None:
    """Register a tool. Enforces FR-011: destructive cannot be auto_run."""
    if descriptor.risk_level == RiskLevel.destructive and descriptor.auto_run:
        raise ToolError("invalid_input", "destructive tools cannot have auto_run=true")
    _REGISTRY[descriptor.name] = (descriptor, executor)


def reset_registry() -> None:
    """Test helper."""
    _REGISTRY.clear()


def get(name: str) -> tuple[ToolDescriptor, Callable[[dict], Awaitable[object]]] | None:
    return _REGISTRY.get(name)


def all_descriptors() -> list[ToolDescriptor]:
    return [d for d, _ in _REGISTRY.values()]


def to_public(descriptor: ToolDescriptor) -> dict:
    return {
        "name": descriptor.name,
        "description": descriptor.description,
        "source_type": descriptor.source_type,
        "input_schema": descriptor.input_schema,
        "risk_level": descriptor.risk_level.value,
        "auto_run": descriptor.auto_run,
        "timeout_seconds": descriptor.timeout_seconds,
    }
