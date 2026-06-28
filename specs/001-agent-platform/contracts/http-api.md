# Contract: HTTP API

**Feature**: 001-agent-platform | **Seam**: backend ↔ frontend (non-realtime)
**Constitution**: principle IV (typed contract; secrets stay backend).

Typed REST over JSON. All mutations except chat (which is WS) are here.
Auth: session cookie. Errors: `{ "error": { "code": "...", "message": "..." } }`.

## Auth

| Method | Path | Body | 200 |
|--------|------|------|-----|
| POST | `/api/auth/register` | `{ email, password }` | `{ user_id }` |
| POST | `/api/auth/login` | `{ email, password }` | sets session cookie |
| POST | `/api/auth/logout` | — | `204` |

## LLM management (FR-019..FR-024)

| Method | Path | Body / Notes |
|--------|------|--------------|
| GET | `/api/llm/providers` | list providers (api_key NEVER returned) |
| POST | `/api/llm/providers` | `{ name, type, base_url, api_key }` — key encrypted at rest (R4) |
| PATCH | `/api/llm/providers/{id}` | update name/base_url; rotate key via `{ api_key }` |
| DELETE | `/api/llm/providers/{id}` | — |
| GET | `/api/llm/models` | list models; `?enabled=true` filter |
| POST | `/api/llm/models` | `{ provider_id, model_name, display_name, input_price_per_1m?, output_price_per_1m? }` |
| PATCH | `/api/llm/models/{id}` | `{ enabled?, display_name?, ... }` (FR-022) |

Rule: no endpoint ever returns `api_key` or its ciphertext.

## Chat sessions (FR-001, FR-015)

| Method | Path | Body / Notes |
|--------|------|--------------|
| GET | `/api/sessions` | list user's sessions |
| POST | `/api/sessions` | `{ model_id, title? }` |
| GET | `/api/sessions/{id}` | session + messages + last activity `seq` |
| DELETE | `/api/sessions/{id}` | — |
| GET | `/api/sessions/{id}/activity?since_seq=N` | replay activity events > N (used on reconnect; SC-006) |

Chat messages are sent over the WebSocket (see `ws-event-protocol.md`),
not HTTP.

## Tools (FR-013)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/tools` | list registered tools with descriptors (name, description, input_schema, risk_level) |

Tool invocation happens via the agent loop (WS-driven), not direct HTTP.

## Scheduled jobs (FR-006, FR-007)

| Method | Path | Body |
|--------|------|------|
| GET | `/api/jobs` | list jobs with last_run_status, next_run_at |
| POST | `/api/jobs` | `{ cron_expr, target_type, target_ref, max_retries? }` |
| PATCH | `/api/jobs/{id}` | `{ status: "active" \| "paused" }` |
| DELETE | `/api/jobs/{id}` | — |
| GET | `/api/jobs/{id}/activity?since_seq=N` | replay that job's activity |
