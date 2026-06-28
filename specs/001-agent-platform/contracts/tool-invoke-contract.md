# Contract: Tool Invoke

**Feature**: 001-agent-platform | **Seam**: backend internal + agent loop
**Constitution**: principle I (Tool-First) — every capability is a tool.

The single uniform interface through which the agent exercises ALL
capabilities (MCP, skills, built-ins, browser, computer). Defined here as
the contract the Tool registry and the agent loop agree on.

## Tool descriptor (registration / discovery)

Every registered tool exposes:

```json
{
  "name": "string  — unique invoke name",
  "description": "string  — what it does (FR-013)",
  "source_type": "mcp | skill | builtin | browser | computer",
  "input_schema": { /* JSON Schema for the tool's arguments (FR-013/FR-014) */ },
  "risk_level": "none | sensitive | destructive",
  "auto_run": false,
  "timeout_seconds": 30
}
```

Rule: if `risk_level == "destructive"`, `auto_run` MUST be `false` (FR-011).

## Invoke (execution)

The agent loop calls a tool by `name` with validated arguments:

```json
// Request (internal call)
{ "name": "browser_navigate", "arguments": { "url": "https://example.com" } }
```

```json
// Response (structured result)
{
  "ok": true,
  "content": [ { "type": "text", "text": "..." } ],
  "error": null
}
```

```json
// Failure
{ "ok": false, "content": [], "error": { "code": "timeout", "message": "..." } }
```

## Behavior guarantees

- **Validation**: arguments MUST be validated against `input_schema` before
  execution; violations return an `error` (`code: "invalid_input"`) and are
  surfaced in the feed without crashing the session (FR-014).
- **Timeout**: every invocation is bounded by `timeout_seconds`; expiry
  returns `error` (`code: "timeout"`) (FR-016).
- **Confirmation gate**: if `risk_level != "none"` and not `auto_run`, the
  invoke path MUST emit a `confirmation_request` and block until resolved
  (see `ws-event-protocol.md`; FR-010). Destructive tools are never
  auto-run regardless of `auto_run` (FR-011).
- **Observability**: every invoke emits a `tool_call` ActivityEvent (with
  inputs) and a `tool_result` ActivityEvent (with the structured result or
  error) — see `data-model.md` (FR-002).
- **Origin mapping**: MCP tools delegate to `session.call_tool(name, arguments)`
  (research R2); skills invoke their callable/subprocess (R3); browser/
  computer tools drive the sandboxed session (R7). All produce the same
  response shape.

## Error codes

| code | meaning |
|------|---------|
| `invalid_input` | arguments failed schema validation |
| `timeout` | exceeded `timeout_seconds` |
| `not_found` | tool name not registered / removed |
| `execution_error` | tool ran and failed |
| `declined` | user declined confirmation (FR-010) |
| `resource_busy` | sandboxed resource locked by another job (R8) |
