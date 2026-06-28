# Quickstart: Agent Platform

**Feature**: 001-agent-platform | **Purpose**: runnable end-to-end validation
**Date**: 2026-06-28

This is a validation/run guide — not implementation. It proves the feature
works end-to-end against the contracts and data model. Implementation
detail belongs in `tasks.md`. References: [data-model.md](data-model.md),
[contracts/](contracts/).

## Prerequisites

- Python 3.11+, Node 20+, an SQL DB (SQLite OK for local).
- An LLM provider API key (OpenAI-compatible or Anthropic).
- Playwright browsers installed (`playwright install chromium`).
- `AGENT_PLATFORM_SECRET_KEY` env var set (Fernet master key — research R4).
- `DATABASE_URL` env var (e.g. `sqlite:///./agent.db` for dev).

## Setup

1. Backend: install deps, run Alembic migrations to create the schema in
   `data-model.md`. Start FastAPI (uvicorn).
2. Frontend: install deps, run Vite dev server pointing at the backend.

(Specific commands/paths are defined in `tasks.md` setup tasks.)

## Validation scenarios

Each maps to a spec user story and is independently runnable.

### V1 — Chat + live activity (US1, P1) — SC-001/SC-002

1. Register a user, log in, create a chat session selecting an enabled model.
2. Open the dashboard WS (`/ws/sessions/{id}`).
3. Send `{ "type": "chat", "content": "What is 2+2? Use a tool if helpful." }`.
4. **Expected**: within 2s, `activity` events stream — at minimum a
   `reasoning` and/or `llm_call` event, then an assistant response. Every
   event has a monotonic `seq`. (contracts: `ws-event-protocol.md`)

### V2 — LLM management (US2, P2) — SC-003a

1. `POST /api/llm/providers` with `{ name, type:"openai_compatible",
   base_url, api_key }`.
2. `POST /api/llm/models` enabling one model.
3. **Expected**: `GET /api/llm/providers` returns the provider with NO
   `api_key` field (FR-018/FR-020). A chat session using that model
   responds (V1), and the `llm_call` activity payload shows model + token
   usage + cost (FR-023).

### V3 — MCP + skills tools (US3, P3) — SC-003

1. Register one MCP server (stdio) and drop one skill manifest in the skills
   dir; restart backend so the tool registry loads them.
2. `GET /api/tools` — **expected**: both tools appear with name,
   description, `input_schema` (FR-013).
3. Ask the agent to perform a task requiring each. **Expected**: the
   `tool_call` event shows the right tool + valid arguments; the
   `tool_result` event returns the structured result (contracts:
   `tool-invoke-contract.md`).

### V4 — Cron scheduling (US4, P4) — SC-004

1. `POST /api/jobs` with `{ cron_expr:"* * * * *", target_type:"tool",
   target_ref:{ tool_id, inputs } }`.
2. Wait ~2 minutes. **Expected**: two job runs appear via
   `GET /api/jobs/{id}/activity`, each with `tool_call`/`tool_result`
   events — zero user interaction (FR-007). `last_run_at`/`next_run_at`
   update.

### V5 — Browser control with confirmation (US5, P5) — SC-005

1. In a chat session, ask the agent to navigate a browser to a URL.
2. **Expected**: a `confirmation_request` activity event streams with
   `risk_level:"sensitive"`; the agent run is blocked (no `tool_result`
   yet).
3. Send `{ "type":"confirmation", "confirmation_id":..., "decision":"approve" }`.
4. **Expected**: a `confirmation_result` event, then `tool_call`/`tool_result`
   for `browser_navigate` streaming the page. Declining instead yields a
   `declined` `tool_result` and the agent does not execute (FR-010).

### V6 — Reconnect / no lost or duplicated events — SC-006

1. Mid-run (during V1 or V5), kill the WS connection.
2. Reconnect and send `{ "type":"resume", "last_seen_seq": N }` with the
   last `seq` seen.
3. **Expected**: all events with `seq > N` replay exactly once; live
   streaming resumes. No lost or duplicated events (contracts:
   `ws-event-protocol.md`).

## Destructive-action guard check (FR-011)

- Register/configure a destructive tool (e.g. a file-delete tool) with
  `risk_level:"destructive"`. **Expected**: it cannot be set to
  `auto_run:true` (rejected), and invoking it always emits a
  `confirmation_request` — never executes without explicit approval.

## Edge-case spot checks (from spec)

- **Concurrent cron on same browser**: schedule two jobs targeting the same
  browser session at the same instant. **Expected**: one runs, the other
  gets a `resource_busy` error (FR, contracts `tool-invoke-contract.md`).
- **Model disabled mid-session**: disable the model a session uses, then
  chat. **Expected**: a clear "model unavailable" error, not a stale run.
- **MCP server unreachable**: point a registered MCP tool at a dead server
  and invoke. **Expected**: `execution_error`/`timeout` in the feed, session
  does not hang.

## Done-when

All of V1–V6 pass, plus the destructive guard and at least the concurrent-
cron edge check. This validates the feature end-to-end against the spec's
success criteria.
