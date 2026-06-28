# Contract: WebSocket Event Protocol

**Feature**: 001-agent-platform | **Seam**: backend ↔ frontend realtime
**Constitution**: principle II (Live Observability) + III (HITL).

One WebSocket channel per dashboard client carries activity streaming AND
confirmation round-trips (research R5/R6). Messages are typed JSON.

## Connection & reconnect

- Endpoint: `GET /ws/sessions/{session_id}` (upgraded to WS).
- On open, the client MAY send `{ "type": "resume", "last_seen_seq": <int> }`.
  The server replays all ActivityEvents with `seq > last_seen_seq` for that
  session, then begins live streaming. (SC-006: no lost or duplicated
  events — client dedups by `seq`.)
- Server sends a `{ "type": "ping" }` periodically; client responds
  `{ "type": "pong" }`. Stale connections are closed server-side.

## Server → Client: activity events

```json
{
  "type": "activity",
  "seq": 42,
  "event": {
    "id": "uuid",
    "type": "reasoning | tool_call | tool_result | llm_call | error | confirmation_request | confirmation_result | progress",
    "tool_id": "uuid | null",
    "payload": { /* type-specific, see below */ },
    "created_at": "ISO-8601"
  }
}
```

`seq` is per-session monotonic (the backfill key). Payload examples:

- `tool_call`: `{ "name": "...", "arguments": {...} }`
- `tool_result`: `{ "ok": true, "content": [...], "error": null }`
- `llm_call`: `{ "model": "...", "prompt_tokens": 120, "completion_tokens": 80, "cost_usd": 0.0021 }` (FR-023)
- `error`: `{ "code": "...", "message": "..." }`
- `confirmation_request`: `{ "confirmation_id": "uuid", "tool": "...", "action_summary": "...", "risk_level": "sensitive | destructive" }`
- `confirmation_result`: `{ "confirmation_id": "uuid", "decision": "approved | declined" }`

## Client → Server: chat input

```json
{ "type": "chat", "content": "user message text" }
```

Server persists a `user` Message, then runs the agent loop, streaming
`activity` events as it goes. The first activity event SHOULD arrive within
2s (SC-001).

## Client → Server: confirmation response

```json
{ "type": "confirmation", "confirmation_id": "uuid", "decision": "approve | decline" }
```

Server resolves the pending ConfirmationRequest, emits a
`confirmation_result` activity event, and unblocks (or rejects) the agent
run. A pending request is NEVER auto-resolved (FR-010/FR-011); if the
client disconnects, the request is retained and re-surfaced on reconnect.

## Sequencing guarantees

- Events are delivered in `seq` order for a given session.
- `tool_call` always precedes its `tool_result`.
- A `confirmation_request` is followed by exactly one `confirmation_result`
  (approved or declined) before the corresponding `tool_result`.
- Reconnect replays by `seq`; the client dedups any `seq` it has already
  rendered (no duplication).
