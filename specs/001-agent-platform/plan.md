# Implementation Plan: Agent Platform

**Branch**: `001-agent-platform` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-agent-platform/spec.md`

## Summary

A self-hosted platform for chatting with an AI agent from a web dashboard and
watching every action it takes stream live. The agent exercises capabilities
— MCP tool servers, locally-defined skills, cron scheduling, browser
automation, and computer control — through one uniform tool-invoke contract.
LLM providers and models are managed in-platform. Sensitive and destructive
actions require explicit user confirmation; nothing risky auto-executes.

Technical approach: a React + TypeScript dashboard over a Python 3.11 FastAPI
backend, talking over a typed HTTP + WebSocket contract. The backend owns the
tool registry, the agent loop, the LLM provider layer, the cron scheduler,
persistence (SQL via SQLAlchemy/Alembic), and sandboxed browser/computer
sessions. A WebSocket channel streams structured activity events to the
dashboard and carries confirmation round-trips.

## Technical Context

**Language/Version**: Python 3.11+ (backend); TypeScript + React 18 (frontend).

**Primary Dependencies**:
- Backend: FastAPI, Uvicorn, SQLAlchemy 2.x, Alembic, Pydantic v2,
  APScheduler (cron), the official MCP Python SDK, Playwright (browser
  automation), an LLM client SDK (provider-specific, behind a provider
  abstraction), `websockets`/Starlette WS for realtime, `httpx`.
- Frontend: React 18, Vite, TypeScript, a WebSocket client, a UI component
  library or native elements (decision in research.md).

**Storage**: SQL — PostgreSQL in production, SQLite for local dev, via
SQLAlchemy. Schema is migration-managed (Alembic). Secrets (LLM API keys)
stored encrypted at rest.

**Testing**: pytest (backend: unit/contract/integration), Vitest (frontend).
Self-checks for non-trivial logic per constitution.

**Target Platform**: Self-hosted web app; backend runs on Linux server or
container; frontend accessed via desktop browser.

**Project Type**: web-service (backend) + web-app (frontend) — a two-project
monorepo.

**Performance Goals**: First activity event within 2s of a chat message
(SC-001); support 10 concurrent active sessions without realtime
degradation (SC-008).

**Constraints**: All tool invocations timeout-bounded (FR-016); secrets
never cross to frontend (FR-018); browser/computer control sandboxed and
least-privilege (FR-017); WS reconnect must not lose or duplicate events
(SC-006).

**Scale/Scope**: Tens of users, single deployment. v1 scope: chat + live
activity (P1), LLM management (P2), MCP+skills (P3), cron (P4),
browser/computer control (P5).

**Unknowns to resolve in research.md**:
- NEEDS CLARIFICATION: LLM provider abstraction — single SDK/protocol vs.
  per-provider adapters; the in-platform provider config approach.
- NEEDS CLARIFICATION: Secret-at-rest encryption approach for API keys.
- NEEDS CLARIFICATION: Confirmation round-trip protocol over WebSocket
  (request shape, agent-blocking semantics, timeout/decline handling).
- NEEDS CLARIFICATION: Browser/computer sandbox boundary (containerized
  browser profile vs. full VM; computer-control scope for v1).
- NEEDS CLARIFICATION: Frontend UI component approach (native vs. a library
  like shadcn/MUI) and WS client/reconnect strategy.
- NEEDS CLARIFICATION: Cron job persistence + scheduler failover/retry
  semantics and concurrency control on shared browser sessions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution: `.specify/memory/constitution.md` v1.0.0.

| Principle | Status | Evidence / Plan |
|-----------|--------|-----------------|
| I. Tool-First Architecture | PASS | FR-003 mandates one uniform tool contract; MCP servers, skills, cron, browser, computer control all registered as tools. data-model.md defines the Tool entity; contracts/ defines the invoke contract. Cron modeled as a scheduler over tools, not a separate path. |
| II. Live Observability (NON-NEGOTIABLE) | PASS | FR-002 + Activity Event entity + WebSocket channel. Every tool call, LLM call (FR-023), reasoning step, error, and confirmation streams as a structured event. No silent execution path in the design. |
| III. Human-in-the-Loop at Trust Boundaries (NON-NEGOTIABLE) | PASS | FR-010/011/012 + Confirmation Request entity + WS round-trip. Browser/computer/mutating actions confirm by default; destructive never auto-run. Edge cases cover pending-confirm-on-disconnect and concurrent-session conflicts. |
| IV. React + Python Boundary | PASS | React/TS frontend, Python/FastAPI backend, typed HTTP+WS contract (contracts/). Backend owns tools, scheduling, persistence, secrets; frontend only renders activity + collects confirmation. |
| V. Simplicity (YAGNI) | PASS | Two-project monorepo (minimum for the React/Python boundary). APScheduler over a custom scheduler; MCP SDK over a hand-rolled protocol. No speculative abstraction; provider abstraction deferred to research.md with a minimal-first default. |

**Gate result**: PASS — no unjustified violations. No Complexity Tracking
entries required. Re-evaluated after Phase 1 design below.

### Post-design re-check (after Phase 1)

Re-evaluated against the generated artifacts (`research.md`, `data-model.md`,
`contracts/`):

| Principle | Post-design status |
|-----------|--------------------|
| I. Tool-First | PASS — `Tool` entity + `tool-invoke-contract.md` enforce one contract; MCP/skills/browser/computer/cron all route through it. Cron runs over the tool path (R8). |
| II. Live Observability | PASS — `ActivityEvent` entity + `ws-event-protocol.md` stream every action; `llm_call`/`tool_call`/`error`/`confirmation_*` all covered. No silent path. |
| III. HITL | PASS — `ConfirmationRequest` entity + WS round-trip block the run; destructive `auto_run` enforced false at write (data-model). Pending requests persist through disconnect. |
| IV. React+Python Boundary | PASS — `http-api.md` + `ws-event-protocol.md` are the typed seam; secrets never in any response (HTTP contract rule). |
| V. Simplicity | PASS — Fernet/APScheduler/native WS/shadcn chosen over heavier alternatives; two projects is the boundary minimum. |

**Post-design gate**: PASS. No new violations introduced by the design.


## Project Structure

### Documentation (this feature)

```text
specs/001-agent-platform/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── agent/           # agent loop, tool-calling orchestration
│   ├── tools/           # tool registry + uniform invoke contract
│   │   ├── mcp/         # MCP server adapters
│   │   ├── skills/      # local skill loaders
│   │   ├── browser/     # Playwright-backed browser tools
│   │   └── computer/    # computer-control tools
│   ├── llm/             # provider abstraction, model registry, secrets
│   ├── scheduler/       # APScheduler cron over tools
│   ├── confirm/         # trust-boundary confirmation engine
│   ├── realtime/        # WebSocket activity streaming + reconnect/backfill
│   ├── api/             # FastAPI routes (HTTP) + WS endpoints
│   ├── models/          # SQLAlchemy ORM entities
│   └── main.py
├── alembic/             # migrations
└── tests/
    ├── unit/
    ├── contract/
    └── integration/

frontend/
├── src/
│   ├── components/      # chat, activity feed, confirmation prompts
│   ├── pages/           # dashboard, llm management, scheduled jobs
│   ├── services/        # WS client + reconnect, API client
│   └── main.tsx
└── tests/
```

**Structure Decision**: Web-application layout (template Option 2). The
React/Python boundary (constitution principle IV) requires two projects;
this is the minimum. `backend/src/` is organized by capability domain
(tools, llm, scheduler, confirm, realtime) so each constitution principle
maps to a clear owner. `frontend/src/` is presentation + WS/API clients
only — no business logic, per principle IV.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations to justify at planning stage. (The two-project split is
mandated by constitution principle IV, not a violation.)

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
