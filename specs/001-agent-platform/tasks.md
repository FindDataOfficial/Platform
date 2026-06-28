# Tasks: Agent Platform

**Input**: Design documents from `/specs/001-agent-platform/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included at constitution-mandated trust boundaries (confirmation gate, tool-invoke contract, scheduling correctness, sandbox isolation) — see `quickstart.md` V1–V6. Per the constitution, non-trivial logic leaves a runnable check behind.

**Organization**: Tasks grouped by user story. Phases follow `plan.md` Project Structure (`backend/`, `frontend/`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1..US5). Setup/Foundational/Polish have no story label.
- Exact file paths in every task.

## Path Conventions

Web app (per `plan.md`): `backend/src/...`, `frontend/src/...`, migrations in `backend/alembic/`.

## Story → priority map (from spec.md)

- US1 — Chat + live activity (P1)
- US2 — LLM management (P2)
- US3 — MCP + skills tools (P3)
- US4 — Cron scheduling (P4)
- US5 — Browser/computer control w/ confirmation (P5)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure.

- [X] T001 Create monorepo structure per `plan.md`: `backend/` and `frontend/` roots, `backend/src/{agent,tools,llm,scheduler,confirm,realtime,api,models}`, `frontend/src/{components,pages,services}`
- [X] T002 Initialize Python 3.11 backend project in `backend/` with `pyproject.toml`: FastAPI, Uvicorn, SQLAlchemy 2.x, Alembic, Pydantic v2, APScheduler, `mcp` SDK, Playwright, `cryptography`, `httpx`, pytest
- [X] T003 [P] Initialize React 18 + Vite + TypeScript frontend in `frontend/` with `package.json`: shadcn/ui, Tailwind, a WS client wrapper, an API client
- [X] T004 [P] Configure backend lint/format (ruff) and frontend lint/format (eslint + prettier)
- [X] T005 [P] Add backend env config loader in `backend/src/config.py` reading `DATABASE_URL`, `AGENT_PLATFORM_SECRET_KEY` (Fernet master key, research R4)
- [X] T006 [P] Install Playwright browsers (`playwright install chromium`) and document the operator step in `backend/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure MUST be complete before ANY user story.

**⚠️ CRITICAL**: No user story work begins until this phase completes. Rationale: US1 (chat) needs the LLM provider layer to run at all, and US2 is its management UI — so the provider abstraction + provider/model entities live here, shared.

- [X] T007 Configure SQLAlchemy engine + session factory in `backend/src/models/db.py` and Alembic env in `backend/alembic/env.py` (PostgreSQL prod / SQLite dev)
- [X] T008 Create base Alembic migration in `backend/alembic/versions/` for all entities in `data-model.md` (User, LlmProvider, LlmModel, Tool, ChatSession, Message, ActivityEvent, ConfirmationRequest, BrowserComputerSession, ScheduledJob)
- [X] T009 [P] Implement Fernet secret encryption helper in `backend/src/llm/secrets.py` (encrypt/decrypt API keys with master key from env; research R4)
- [X] T010 [P] Implement auth middleware in `backend/src/api/auth.py` (session cookie, argon2 password hashing, register/login/logout endpoints per `contracts/http-api.md`)
- [X] T011 [P] Implement the LLM provider abstraction in `backend/src/llm/provider.py`: `LlmProvider` protocol returning normalized `{text, tool_calls, usage, cost}`; OpenAI-compatible adapter + Anthropic adapter in `backend/src/llm/adapters/` (research R1)
- [X] T012 Implement session-scoped WebSocket foundation in `backend/src/realtime/` : accept `/ws/sessions/{id}`, per-session monotonic `seq`, `resume`/`last_seen_seq` backfill from persisted ActivityEvent (research R5, `contracts/ws-event-protocol.md`)
- [X] T013 [P] Implement FastAPI error envelope + timeout/exception handlers in `backend/src/api/errors.py` returning `{error:{code,message}}` per `contracts/http-api.md`
- [X] T014 Foundational trust-boundary check: contract test in `backend/tests/contract/test_tool_invoke_contract.py` proving the tool-invoke contract (validation, timeout, error codes from `contracts/tool-invoke-contract.md`) — write first, must pass after T020

**Checkpoint**: Foundation ready — user story implementation can begin (US1 first).

---

## Phase 3: User Story 1 — Chat with AI and Watch It Work (Priority: P1) 🎯 MVP

**Goal**: User chats with the AI in the dashboard; every action streams live.
**Independent Test**: `quickstart.md` V1 — send a chat message, see `reasoning`/`llm_call` activity events stream within 2s (SC-001/SC-002).

### Tests for User Story 1

- [X] T015 [P] [US1] Contract test in `backend/tests/contract/test_ws_event_protocol.py` proving seq ordering, tool_call-before-tool_result, and reconnect backfill (SC-006)

### Implementation for User Story 1

- [X] T016 [P] [US1] Create ORM models User, LlmProvider, LlmModel, ChatSession, Message, ActivityEvent in `backend/src/models/` (fields/validation per `data-model.md`)
- [X] T017 [US1] Implement the agent loop in `backend/src/agent/loop.py`: take a chat message, call the selected LlmModel via the provider layer, emit ActivityEvents (`reasoning`, `llm_call` with model+tokens+cost per FR-023), repeat until response complete
- [X] T018 [US1] Wire WS chat input → agent loop in `backend/src/realtime/`: on `{type:chat}`, persist Message, run loop, stream `activity` events (first event <2s, SC-001)
- [X] T019 [US1] Implement HTTP endpoints in `backend/src/api/sessions.py`: list/create/get/delete sessions, `GET /sessions/{id}/activity?since_seq=N` (`contracts/http-api.md`)
- [X] T020 [US1] Implement tool registry + invoke core in `backend/src/tools/registry.py` and `backend/src/tools/invoke.py`: descriptor + JSON-schema validation + timeout + structured result (no tools registered yet; built-ins added in later stories) per `contracts/tool-invoke-contract.md`
- [X] T021 [P] [US1] Build frontend dashboard shell in `frontend/src/pages/Dashboard.tsx`: chat input + activity feed rendering `activity` events by type
- [X] T022 [P] [US1] Build frontend WS client in `frontend/src/services/ws.ts`: native WebSocket, auto-reconnect, `resume`+`last_seen_seq` backfill, dedup by `seq` (research R5/R9)
- [X] T023 [P] [US1] Build frontend API client in `frontend/src/services/api.ts`: typed wrappers for `contracts/http-api.md`

**Checkpoint**: US1 fully functional and independently testable (V1 passes).

---

## Phase 4: User Story 2 — Manage LLM Providers and Models (Priority: P2)

**Goal**: Operator registers providers/models, stores keys as backend secrets, selects a model per session.
**Independent Test**: `quickstart.md` V2 — register provider, enable model, chat against it; `llm_call` shows tokens+cost; `api_key` never returned (SC-003a).

### Implementation for User Story 2

- [X] T024 [P] [US2] Implement LLM provider CRUD in `backend/src/api/llm.py`: create/update/delete providers, encrypt key via T009, NEVER return `api_key`/ciphertext (`contracts/http-api.md`, FR-018/FR-020)
- [X] T025 [P] [US2] Implement model CRUD + enable/disable in `backend/src/api/llm.py`: `POST/PATCH /models`, `enabled` toggle (FR-022); disabling yields "model unavailable" on existing sessions (edge case)
- [X] T026 [US2] Implement provider failover in `backend/src/llm/provider.py`: on invalid/expired key, rate-limit, or model-unavailable, report error in feed and fail over to an enabled alternative when configured (FR-024, edge case)
- [X] T027 [P] [US2] Build frontend LLM management page in `frontend/src/pages/LlmManagement.tsx`: provider/model forms (no key field ever displays), enable/disable toggles
- [X] T028 [P] [US2] Add model selector to session creation UI in `frontend/src/pages/Dashboard.tsx` (only enabled models offered)

**Checkpoint**: US2 functional (V2 passes); US1 now configurable end-to-end.

---

## Phase 5: User Story 3 — Run Tools via MCP and Skills (Priority: P3)

**Goal**: Register MCP servers + skills; agent invokes them through the uniform tool contract.
**Independent Test**: `quickstart.md` V3 — register one MCP server + one skill, `GET /tools` lists both with schemas, agent invokes each (SC-003).

### Tests for User Story 3

- [X] T029 [P] [US3] Contract test in `backend/tests/contract/test_mcp_adapter.py` proving `list_tools()`/`call_tool()` map into the tool-invoke contract (research R2)

### Implementation for User Story 3

- [X] T030 [US3] Implement MCP adapter in `backend/src/tools/mcp/`: connect via official `mcp` SDK (stdio + streamable_http), wrap each `list_tools()` entry into a registered Tool, delegate invoke to `call_tool(name, arguments)` (research R2)
- [X] T031 [P] [US3] Implement skill loader in `backend/src/tools/skills/`: read manifests (name, description, input_schema) + entry point (callable or subprocess) from a configured skills dir, register as Tools (research R3)
- [X] T032 [US3] Wire the tool registry into the agent loop in `backend/src/agent/loop.py`: expose tool descriptors to the LLM, execute requested tool calls via `invoke.py`, emit `tool_call`/`tool_result` ActivityEvents
- [X] T033 [P] [US3] Implement `GET /api/tools` in `backend/src/api/tools.py` returning descriptors (FR-013, `contracts/http-api.md`)
- [X] T034 [P] [US3] Add a tool-invocation indicator to the frontend activity feed in `frontend/src/components/ActivityFeed.tsx` (render tool name + args + result)

**Checkpoint**: US3 functional (V3 passes); the agent can now act via tools.

---

## Phase 6: User Story 4 — Schedule Recurring Tasks with Cron (Priority: P4)

**Goal**: Schedule tools/chat on cron; runs auto-execute and appear in the feed.
**Independent Test**: `quickstart.md` V4 — create a `* * * * *` job, two runs appear with `tool_call`/`tool_result`, zero interaction (SC-004).

### Tests for User Story 4

- [X] T035 [P] [US4] Test in `backend/tests/unit/test_scheduler.py` proving APScheduler SQLJobstore survives a restart and a missed/failed run retries per policy (research R8)

### Implementation for User Story 4

- [X] T036 [US4] Implement cron scheduler in `backend/src/scheduler/`: APScheduler with persistent SQL jobstore, jobs run through the agent/tool path emitting ActivityEvent with `job_id` set (FR-007, research R8)
- [X] T037 [US4] Implement per-resource lock in `backend/src/scheduler/locks.py`: serialize jobs targeting the same BrowserComputerSession; reject overlap with `resource_busy` (edge case, R8)
- [X] T038 [US4] Implement job CRUD in `backend/src/api/jobs.py`: create/pause/delete, list with `last_run_status`/`next_run_at`, `GET /jobs/{id}/activity?since_seq=N` (FR-006/FR-007, `contracts/http-api.md`)
- [X] T039 [P] [US4] Build frontend scheduled-jobs page in `frontend/src/pages/ScheduledJobs.tsx`: create/list/pause jobs, view a job's activity feed

**Checkpoint**: US4 functional (V4 passes); platform is now an autonomous worker.

---

## Phase 7: User Story 5 — Browser and Computer Control with Confirmation (Priority: P5)

**Goal**: Agent drives browser/computer in a sandbox; sensitive/destructive actions confirm.
**Independent Test**: `quickstart.md` V5 — propose a browser nav, confirm via WS, watch steps stream; declining yields a `declined` result (SC-005). Plus destructive guard (FR-011).

### Tests for User Story 5

- [X] T040 [P] [US5] Test in `backend/tests/unit/test_confirmation_gate.py` proving a destructive tool can never be `auto_run` and always emits a `confirmation_request`; pending request is never auto-resolved (FR-010/FR-011)

### Implementation for User Story 5

- [X] T041 [US5] Implement the confirmation engine in `backend/src/confirm/`: emit `confirmation_request` ActivityEvent + ConfirmationRequest row, block the agent run on an `asyncio.Future` until WS response, never auto-approve, persist through disconnect (research R6, FR-010/FR-011/FR-012)
- [X] T042 [US5] Wire confirmation into the tool invoke path in `backend/src/tools/invoke.py`: if `risk_level != none` and not `auto_run`, gate via the confirmation engine; destructive ignores `auto_run` (T014 contract enforced)
- [X] T043 [US5] Implement browser tools in `backend/src/tools/browser/`: Playwright with an isolated profile per BrowserComputerSession; `browser_navigate`/click/read as Tools streaming `progress` events (research R7, FR-008/FR-017)
- [X] T044 [P] [US5] Implement computer-control tools in `backend/src/tools/computer/`: mouse/keyboard/screen scoped to the prepared sandbox, not the operator desktop unless explicit per-session opt-in (FR-009/FR-017)
- [X] T045 [US5] Handle `confirmation` WS messages in `backend/src/realtime/`: resolve the Future, emit `confirmation_result`, approve→execute / decline→`declined` tool_result (research R6, `contracts/ws-event-protocol.md`)
- [X] T046 [P] [US5] Build frontend confirmation prompt in `frontend/src/components/ConfirmationPrompt.tsx`: render pending `confirmation_request`, send approve/decline over WS

**Checkpoint**: US5 functional (V5 + destructive guard pass).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Affects multiple stories.

- [X] T047 [P] Add reconnect/edge-case integration tests in `backend/tests/integration/`: WS drop mid-run + backfill (SC-006), concurrent cron on same browser (R8), MCP server unreachable (edge case)
- [X] T048 [P] Add backend structured logging + audit log of trust-boundary decisions (actor, target, outcome) per FR-012 in `backend/src/api/audit.py`
- [X] T049 [P] Documentation: operator runbook in `docs/runbook.md` (secret key rotation R4, sandbox provisioning R7, skills/MCP registration)
- [X] T050 Run `quickstart.md` V1–V6 end-to-end validation; fix failures
- [X] T051 [P] Frontend polish: loading/empty/error states across Dashboard, LlmManagement, ScheduledJobs in `frontend/src/components/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS all user stories. Provider layer (T011) + WS (T012) + tool-invoke core (T020) are the shared spine.
- **US1 (Phase 3)**: depends on Foundational. MVP.
- **US2 (Phase 4)**: depends on Foundational (T011) + US1 session model; refines the provider UI/CRUD US1 already uses.
- **US3 (Phase 5)**: depends on US1 (agent loop + tool registry T020) — tools plug into the existing invoke path.
- **US4 (Phase 6)**: depends on US3 (cron schedules tools) + US1 (observability).
- **US5 (Phase 7)**: depends on US3 (tool registry) + Foundational WS (T012) for the confirmation round-trip.
- **Polish (Phase 8)**: after all desired stories complete.

### User Story Dependencies

- **US1 (P1)**: starts after Foundational. No story deps — MVP.
- **US2 (P2)**: after Foundational; shares the provider layer with US1.
- **US3 (P3)**: after US1 (needs the agent loop + tool registry to invoke tools).
- **US4 (P4)**: after US3 (schedules tools) and US1 (observes runs).
- **US5 (P5)**: after US3 (registers browser/computer as tools) + Foundational WS.

### Within Each User Story

- Tests (where present) written FIRST and failing before implementation.
- Models before services; services before endpoints; endpoints before UI.
- Story complete before next priority.

### Parallel Opportunities

- Phase 1: T003/T004/T005/T006 parallel.
- Phase 2: T009/T010/T011/T013 parallel (different files).
- US1: T016 (models) parallel with T021/T022/T023 (frontend) — different repos.
- US2: T024/T025/T027/T028 parallel.
- US3: T031/T033/T034 parallel once T030 lands.
- US5: T044 (computer tools) parallel with T046 (frontend prompt).

---

## Parallel Example: User Story 1

```bash
# Backend model layer + frontend shell/clients run concurrently (different repos):
Task: "Create ORM models in backend/src/models/ (T016)"
Task: "Build frontend dashboard shell in frontend/src/pages/Dashboard.tsx (T021)"
Task: "Build frontend WS client in frontend/src/services/ws.ts (T022)"
Task: "Build frontend API client in frontend/src/services/api.ts (T023)"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational).
2. Complete Phase 3 (US1): chat + live activity streaming.
3. **STOP and VALIDATE**: run `quickstart.md` V1 (SC-001/SC-002).
4. Demo/deploy if ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. + US1 → chat works (MVP).
3. + US2 → operator configures LLMs (V2).
4. + US3 → agent acts via tools (V3).
5. + US4 → autonomous scheduled runs (V4).
6. + US5 → browser/computer control with confirmation (V5).
7. Each story adds value without breaking prior stories.

---

## Notes

- [P] = different files, no dependencies. [USx] maps a task to its story.
- Tests are included only at constitution-mandated trust boundaries (confirmation gate, tool-invoke contract, scheduling/restart, sandbox) and quickstart validation — not a per-function suite.
- Verify tests fail before implementing them.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently via `quickstart.md`.
