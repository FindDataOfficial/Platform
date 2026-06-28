# Data Model: Agent Platform

**Feature**: 001-agent-platform | **Phase**: 1 | **Date**: 2026-06-28
**Storage**: SQL (PostgreSQL prod / SQLite dev) via SQLAlchemy 2.x + Alembic.

Entities derived from `spec.md` Key Entities + `research.md` decisions.
Field types are logical (SQL column types in parens where it matters).
`id` fields are UUIDs (server-generated) unless noted.

---

## User

A platform user (operator/end user). v1: single authenticated-user model.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| email | string | unique, not null |
| password_hash | string | not null (argon2) |
| created_at | timestamp | not null |

**Validation**: email format; password minimum length at the trust boundary.
**Relationships**: 1→many ChatSession, ScheduledJob, LlmProvider (owner).

---

## LlmProvider

A registered model provider (research R1). Owns the encrypted API credential.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| owner_id | UUID | FK→User, not null |
| name | string | display name, not null |
| type | enum | `openai_compatible` \| `anthropic` |
| base_url | string | not null |
| api_key_ciphertext | bytes | Fernet-encrypted (R4), not null |
| created_at | timestamp | not null |

**Validation**: `type` in allowed set; `base_url` is a valid URL.
**Secrets**: `api_key_ciphertext` only — plaintext key never persisted, never
sent to frontend (FR-018/FR-020). Decrypted in-backend at call time only.
**Relationships**: 1→many LlmModel.

---

## LlmModel

A model offered by a provider, selectable per session/job (research R1).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| provider_id | UUID | FK→LlmProvider, not null |
| model_name | string | provider's model id, not null |
| display_name | string | not null |
| enabled | bool | default true (FR-022) |
| input_price_per_1m | numeric | nullable, for cost estimate |
| output_price_per_1m | numeric | nullable, for cost estimate |
| created_at | timestamp | not null |

**Validation**: `(provider_id, model_name)` unique.
**State transitions**: `enabled` true↔false (operator action); disabling does
not delete — existing sessions surface "model unavailable" (edge case).
**Relationships**: many→1 LlmProvider; referenced by ChatSession, ScheduledJob.

---

## Tool

A registered capability behind the uniform invoke contract (research R1–R3).
One row per discoverable tool, regardless of origin.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| name | string | unique, not null (invoke name) |
| description | string | not null (FR-013) |
| source_type | enum | `mcp` \| `skill` \| `builtin` \| `browser` \| `computer` |
| source_ref | string | origin identifier (MCP server id, skill path, etc.) |
| input_schema | json | JSON Schema, not null (FR-013/FR-014) |
| risk_level | enum | `none` \| `sensitive` \| `destructive` (FR-010/FR-011) |
| auto_run | bool | default false (FR-010); false always if destructive |
| timeout_seconds | int | not null (FR-016) |
| created_at | timestamp | not null |

**Validation**: `input_schema` is a valid JSON Schema; if `risk_level =
destructive`, `auto_run` MUST be false (enforced at write — FR-011).
**State transitions**: registered → (enabled/disabled) → unregistered.
Removal while a ScheduledJob references it → job fails clearly on next run
(edge case).
**Relationships**: referenced by ActivityEvent (tool calls), ScheduledJob.

---

## ChatSession

A conversation between a user and the assistant (FR-001/FR-015).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| owner_id | UUID | FK→User, not null |
| model_id | UUID | FK→LlmModel, not null |
| title | string | nullable |
| created_at | timestamp | not null |
| updated_at | timestamp | not null |

**Relationships**: 1→many Message, ActivityEvent; 1→0..1 BrowserComputerSession.

---

## Message

A single chat entry (user / assistant / system).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| session_id | UUID | FK→ChatSession, not null |
| role | enum | `user` \| `assistant` \| `system` |
| content | text | not null |
| seq | int | per-session monotonic, not null |
| created_at | timestamp | not null |

**Validation**: `role` in allowed set; `(session_id, seq)` unique.

---

## ActivityEvent

The single source of truth for the dashboard feed (constitution principle II;
research R5). One row per agent action.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| session_id | UUID | FK→ChatSession (nullable for headless scheduled runs) |
| job_id | UUID | FK→ScheduledJob, nullable |
| seq | bigint | per-(session or job) monotonic, not null (R5 backfill key) |
| type | enum | `reasoning` \| `tool_call` \| `tool_result` \| `llm_call` \| `error` \| `confirmation_request` \| `confirmation_result` \| `progress` |
| tool_id | UUID | FK→Tool, nullable |
| payload | json | type-specific structured data (inputs, result, tokens, cost, error) |
| created_at | timestamp | not null |

**Validation**: exactly one of `session_id`/`job_id` set; `seq` monotonic
within that scope. `llm_call` payload includes model, token usage, cost
(FR-023).
**Relationships**: belongs to a session or a scheduled run.

---

## ConfirmationRequest

A pending approval for a trust-boundary action (research R6; FR-010..FR-012).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| session_id | UUID | FK→ChatSession, not null |
| activity_event_id | UUID | FK→ActivityEvent (the `confirmation_request` event), not null |
| tool_id | UUID | FK→Tool, not null |
| action_summary | string | human-readable, not null |
| risk_level | enum | `sensitive` \| `destructive` |
| status | enum | `pending` \| `approved` \| `declined` \| `superseded` |
| decided_at | timestamp | nullable |
| decided_by | UUID | FK→User, nullable |

**State transitions**: `pending` → `approved` | `declined` (user response);
never auto-transitions to approved (FR-010/FR-011). Persisted so a
disconnect cannot lose or auto-resolve it (edge case).
**Relationships**: 1→1 ActivityEvent (the request); produces a
`confirmation_result` ActivityEvent on resolution.

---

## BrowserComputerSession

A sandboxed execution context for browser/computer control (research R7;
FR-017).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| session_id | UUID | FK→ChatSession, not null |
| kind | enum | `browser` \| `computer` |
| profile_dir | string | isolated Playwright profile path, not null |
| status | enum | `idle` \| `busy` \| `closed` |
| created_at | timestamp | not null |

**Validation/concurrency**: a per-row lock serializes concurrent tool calls
targeting the same session (R8); `busy` state rejects overlapping jobs with
a clear error (edge case: concurrent cron on same browser).

---

## ScheduledJob

A recurring cron schedule targeting a tool or chat instruction (research R8;
FR-006/FR-007).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| owner_id | UUID | FK→User, not null |
| cron_expr | string | 5-field cron, not null |
| target_type | enum | `tool` \| `chat` |
| target_ref | json | tool id + inputs, or chat instruction + model_id |
| max_retries | int | default 3 |
| status | enum | `active` \| `paused` \| `failed` |
| last_run_at | timestamp | nullable |
| last_run_status | enum | `success` \| `failed` \| `running` \| nullable |
| next_run_at | timestamp | nullable |
| created_at | timestamp | not null |

**Validation**: `cron_expr` is a valid 5-field expression; if `target_type=
tool`, referenced Tool must exist (else job fails clearly on next run —
edge case).
**State transitions**: `active` ↔ `paused` (operator); `active` → `failed`
after exhausted retries. Runs emit ActivityEvent rows with `job_id` set.

---

## Entity relationship summary

```
User 1──* ChatSession 1──* Message
                 │ 1──* ActivityEvent *──1 Tool
                 │ 1──1 BrowserComputerSession
                 │ 1──* ConfirmationRequest *──1 Tool
User 1──* ScheduledJob *──? Tool  (target)
ScheduledJob 1──* ActivityEvent
User 1──* LlmProvider 1──* LlmModel
LlmModel 1──* ChatSession   (selected model)
LlmModel 1──* ScheduledJob  (selected model for chat jobs)
```
