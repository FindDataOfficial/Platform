"""MCP adapter (T030, US3, research R2).

Connects to an external MCP server via the official `mcp` Python SDK (stdio or
streamable_http), wraps each `list_tools()` entry into a registered Tool, and
delegates invocation to `call_tool(name, arguments)`. All MCP tools land behind
the uniform tool contract (constitution I).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from src.models.entities import RiskLevel
from src.tools.registry import ToolDescriptor, register

logger = logging.getLogger(__name__)


@dataclass
class McpServerConfig:
    server_id: str  # logical id; used as source_ref
    name: str
    transport: str  # "stdio" | "streamable_http"
    # stdio: command + args; http: url
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None


_REGISTERED: set[str] = set()  # server_ids already wrapped


def _make_executor(server_id: str, session_holder: dict):
    async def _exec(arguments: dict) -> dict:
        sess = session_holder.get("session")
        if sess is None:
            raise RuntimeError("MCP session not initialized")
        result = await sess.call_tool(session_holder["tool_name"], arguments)
        # Normalize MCP content blocks into a plain payload.
        texts = []
        for block in getattr(result, "content", []) or []:
            t = getattr(block, "text", None)
            if t is not None:
                texts.append(t)
        return {"text": "\n".join(texts), "raw": [str(b) for b in getattr(result, "content", []) or []]}

    return _exec


async def wrap_server(config: McpServerConfig, risk_level: RiskLevel = RiskLevel.none) -> list[ToolDescriptor]:
    """Connect to the MCP server and register all its tools. Returns descriptors."""
    # Lazy imports: the mcp SDK is an optional-heavy dep; keep it local.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    if config.transport == "stdio":
        params = StdioServerParameters(
            command=config.command or "",
            args=config.args or [],
            env=config.env or None,
        )
        ctx = stdio_client(params)
    else:
        ctx = streamable_http_client(config.url or "")

    read, write = await ctx.__aenter__()
    session = ClientSession(read, write)
    await session.__aenter__()
    await session.initialize()
    tools = await session.list_tools()

    descriptors: list[ToolDescriptor] = []
    for t in tools.tools:
        # JSON schema from the MCP tool's inputSchema.
        schema = getattr(t, "inputSchema", None) or {"type": "object", "properties": {}}
        holder = {"session": session, "tool_name": t.name}
        desc = ToolDescriptor(
            name=f"mcp_{config.server_id}_{t.name}",
            description=t.description or f"MCP tool {t.name} from {config.name}",
            source_type="mcp",
            input_schema=schema,
            risk_level=risk_level,
            timeout_seconds=60,
        )
        register(desc, _make_executor(config.server_id, holder))
        descriptors.append(desc)
    _REGISTERED.add(config.server_id)
    logger.info("registered %d MCP tools from %s", len(descriptors), config.name)
    return descriptors


def is_registered(server_id: str) -> bool:
    return server_id in _REGISTERED
