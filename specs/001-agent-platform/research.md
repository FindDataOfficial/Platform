# Research: Agent Platform

**Feature**: 001-agent-platform | **Phase**: 0 | **Date**: 2026-06-28

Resolves every NEEDS CLARIFICATION from `plan.md` Technical Context and
records the best-practice/pattern decisions behind each technology choice.
Each item: **Decision**, **Rationale**, **Alternatives considered**.

---

## R1. LLM provider abstraction (FR-019..FR-024)

**Decision**: A thin in-process provider abstraction (`LlmProvider` protocol)
with two adapters shipping in v1 — an **OpenAI-compatible** adapter and an
**Anthropic** adapter. The operator registers a provider by type + base URL
+ API key; enabled models are selectable per session/job. Each LLM call
returns a normalized result (text, tool-call requests, token usage, cost
estimate) consumed by the agent loop.

**Rationale**: The OpenAI-compatible Chat Completions API is the de facto
interchange standard — one adapter covers OpenAI, local (Ollama, vLLM),
OpenRouter, Together, Groq, and most gateways via `base_url`. Adding the
Anthropic adapter covers the second major native API. A protocol with two
implementations is justified, not speculative: the constitution's LLM-
management requirement (FR-019) explicitly demands multi-provider support,
so a single hard-coded SDK would violate it. Cost is estimated from a
configurable per-model price table; no external billing API.

**Alternatives considered**:
- **LiteLLM / one unified SDK** — covers 100+ providers in one call. Rejected
  for v1: it's a heavy dependency and an extra abstraction layer we don't
  need for two providers; the uniform interface we need is our own tool/LLM
  contract, not LiteLLM's. Upgrade path if provider count grows past ~4.
- **Single OpenAI SDK only** — rejected: violates FR-019 (multi-provider)
  and locks the operator to one vendor.
- **Provider-specific code in the agent loop** — rejected: violates
  constitution principle V (simplicity of the seam) and couples the loop to
  vendors.

---

## R2. MCP integration (FR-004, FR-013)

**Decision**: Use the **official MCP Python SDK** (`mcp` package,
`/modelcontextprotocol/python-sdk`, v1.12.x) as a client. Each registered
MCP server is wrapped by an adapter that, on connect, calls
`session.list_tools()` and registers every remote tool into the platform's
tool registry under a uniform contract (name, JSON-schema input, executor).
Tool execution delegates to `session.call_tool(name, arguments)` and
normalizes the returned content into the platform's structured result.
Support both **stdio** (local servers) and **streamable_http / SSE**
(remote servers) transports, selected per registered server.

**Rationale**: Verified against current SDK docs. `ClientSession` exposes
exactly the two operations the platform needs — `list_tools()` and
`call_tool(name, arguments)` — and the SDK owns all transport/versioning
complexity. Wrapping remote tools into our own registry means the agent
loop and the activity feed treat MCP tools identically to skills and
built-ins (constitution principle I: one uniform contract). Building a
hand-rolled MCP client would be re-inventing the protocol (violates V).

**Alternatives considered**:
- **Hand-rolled MCP client over JSON-RPC** — rejected: re-implements
  protocol framing, version negotiation, and transports the SDK already
  provides.
- **Treat MCP servers as opaque, no registry mapping** — rejected: breaks
  the uniform tool contract and discoverability (FR-013).

---

## R3. Skills (FR-005, FR-013)

**Decision**: A skill is a locally-defined tool packaged as a directory with
a manifest (name, description, input JSON schema) and an executable entry
point (a Python callable or a subprocess script). A loader reads skill
manifests from a configured skills directory and registers each as a tool
under the same contract as MCP tools. Execution runs the callable/script
with validated inputs and returns structured output.

**Rationale**: Mirrors the Claude-Code skills model the user referenced.
Keeping skills on the same tool contract as MCP (R2) satisfies principle I
with no separate execution path. Subprocess entry points let skills be any
language; Python callables avoid subprocess overhead for native ones.

**Alternatives considered**:
- **Skills as a separate, non-tool capability** — rejected: violates
  principle I (tool-first) and FR-003.
- **Only Python-callable skills** — rejected: would prevent wrapping
  existing CLI/script skills; subprocess entry is the minimal general form.

---

## R4. Secret-at-rest encryption for LLM API keys (FR-018, FR-020)

**Decision**: Symmetric encryption with **Fernet** (`cryptography` package).
A single master key is loaded from an environment variable
(`AGENT_PLATFORM_SECRET_KEY`) at startup; provider API keys are encrypted
on write and decrypted only in-backend at call time. The master key never
persists to the DB and never crosses to the frontend.

**Rationale**: Fernet is audited, authenticated (tamper-evident), and a
one-line API — the minimal correct choice (principle V). Decryption happens
inside the backend's LLM provider layer, so secrets never reach the
contract (FR-018). Rotating the master key requires re-encrypting all
stored keys (documented as an operator runbook task, not v1 automation).

**Alternatives considered**:
- **OS keyring** — rejected: machine-bound; awkward for a server/container
  deployment shared across processes, and not portable to a DB row.
- **HashiCorp Vault** — rejected: operationally heavy for a tens-of-users
  self-hosted deployment (YAGNI); note as upgrade path if multi-tenant.
- **Plaintext DB column** — rejected: violates FR-020 and basic secrecy.

---

## R5. Realtime activity streaming + reconnect (FR-002, SC-006)

**Decision**: A single **WebSocket** channel per dashboard client carries
activity events. Each event has a **monotonic per-session sequence ID**.
The backend persists every event as it is emitted (Activity Event entity),
so on reconnect the client sends its `last_seen_seq` and the server replays
any missing events, then resumes live streaming. New events during
disconnection are simply buffered in the persisted store — no special
queue. Frontend uses a native `WebSocket` with an auto-reconnect loop
(exponential backoff) and seq-based backfill on open.

**Rationale**: Persisting events as the source of truth (constitution
principle II: events ARE the feed) makes reconnect correctness trivial —
"missed" events are just "not yet sent," replayed by seq. This satisfies
SC-006 (no lost or duplicated events: dedup by seq on the client). No
external message broker needed for tens of users (YAGNI).

**Alternatives considered**:
- **Server-Sent Events (SSE)** — rejected: one-way; the channel also needs
  to carry confirmation responses upstream (R6), so WebSocket is required
  anyway. Don't run two channels.
- **Redis Pub/Sub / message broker** — rejected: overkill at this scale;
  the persisted-event + seq-replay model needs no broker. Upgrade path if
  concurrent sessions exceed ~100.
- **Polling** — rejected: violates the "live" requirement (SC-001).

---

## R6. Confirmation round-trip protocol (FR-010..FR-012)

**Decision**: Confirmation rides on the same WebSocket (R5). When the agent
reaches a trust-boundary action, the backend:
1. Emits a `confirmation_request` activity event (id, tool, action summary,
   risk level: `sensitive` | `destructive`) and **blocks the agent run**
   awaiting a response.
2. The dashboard renders a prompt and sends a `confirmation_response`
   message (id, decision: `approve` | `decline`).
3. The backend resolves the run: on approve, executes; on decline, returns
   a rejection to the agent (which continues reasoning and reports it).
4. **No auto-approve.** A request with no response holds indefinitely while
   the session is connected; if the client disconnects, the pending request
   is retained and re-surfaced on reconnect (never silently approved).
   Destructive actions additionally cannot be auto-approved even via the
   per-class opt-in flag (FR-011).

**Rationale**: Blocking the run on a future is the simplest correct model —
the agent loop awaits an `asyncio.Future` resolved by the WS handler.
Persisting the pending request (Confirmation Request entity) means a
disconnect can't auto-approve or lose the decision (SC-005, edge case:
pending-confirm-on-disconnect). One channel for both activity and
confirmation avoids protocol sprawl (principle V).

**Alternatives considered**:
- **HTTP polling for confirmations** — rejected: adds a second mechanism
  alongside WS; slower and more complex.
- **Auto-approve with a global flag** — rejected: violates FR-010
  (confirmation is the default) and FR-011 (destructive never auto-run).
- **Timeout → auto-approve** — explicitly rejected for destructive; for
  sensitive, an optional per-class timeout may decline (never approve) —
  left as a v1.1 refinement, default is hold.

---

## R7. Browser & computer-control sandbox (FR-008, FR-009, FR-017)

**Decision**: v1 uses **Playwright** for browser automation, launched with
an **isolated browser profile** in a dedicated, operator-configured data
directory (never the operator's personal profile). Browser and computer-
control sessions run in that sandboxed context. Computer control (mouse,
keyboard, screen) is scoped to the **same sandboxed environment** (e.g. a
container or dedicated user account the operator provisions), not the
operator's primary desktop, unless the operator explicitly opts in per
session. Every action goes through the confirmation gate (R6) and streams
as activity events.

**Rationale**: Playwright is the established, well-maintained browser-
automation library with a Python API; isolated profiles give sandboxing
without a full VM (minimal for tens of users — principle V). Scoping
computer control to a prepared sandbox honors FR-017 (least-privilege,
sandboxed) and the constitution's HITL principle. A full per-action VM is
deferred (YAGNI at this scale).

**Alternatives considered**:
- **Selenium** — rejected: Playwright has a cleaner async API and better
  modern-web support; Selenium adds a driver-process layer.
- **Full VM per session** — rejected for v1: heavy; upgrade path if
  untrusted skills/scripts are introduced.
- **Computer control on the operator's real desktop by default** —
  rejected: violates FR-017 and the HITL principle; only via explicit opt-in.

---

## R8. Cron scheduling (FR-006, FR-007, FR-016)

**Decision**: **APScheduler** with a **persistent SQL jobstore** (same DB
as everything else) so scheduled jobs survive backend restarts. A scheduled
job targets a tool (or a chat instruction) and runs it through the normal
agent/tool path — every run emits activity events into the feed (FR-007).
Retry policy is configurable (max retries + backoff); a failed run is
logged as an activity event and retried per policy. **Concurrency control:**
a per-resource lock (e.g. per browser/computer session) serializes jobs
that target the same sandboxed resource; if busy, the overlapping job is
rejected with a clear error rather than producing undefined behavior (edge
case: concurrent cron on the same browser).

**Rationale**: APScheduler's SQLJobStore gives persistence + cron
expressions without a separate scheduler service (principle V; stdlib-
adjacent). Running scheduled jobs through the same tool path means
observability (principle II) and the confirmation gate (R6) apply
identically — cron is a scheduler *over* tools, not a separate execution
path (constitution principle I). The per-resource lock is the minimal
correct fix for the concurrent-browser edge case.

**Alternatives considered**:
- **Custom cron loop with `apscheduler` in-memory only** — rejected: jobs
  lost on restart (violates FR-015 persistence).
- **Celery / a separate task queue** — rejected: operationally heavy at
  this scale (YAGNI); the in-process scheduler with a SQL jobstore suffices.
- **No concurrency control (let jobs race)** — rejected: produces undefined
  behavior on shared browser sessions (explicit edge case in spec).

---

## R9. Frontend UI + WS client (FR-001, FR-002, R5)

**Decision**: **React 18 + Vite + TypeScript**. UI built with **shadcn/ui**
(Radix primitives + Tailwind) for accessible, copy-in components with no
heavy runtime dependency. The dashboard has three surfaces: the chat +
live activity feed, an LLM-management page, and a scheduled-jobs page.
The WS client is a small native-`WebSocket` wrapper with auto-reconnect
and seq-based backfill (R5); an API client wraps the typed HTTP contract.

**Rationale**: shadcn/ui gives accessible, owned components without a
runtime component library lock-in (principle V — copy-in beats a dependency
tree). The frontend holds no business logic: it renders activity events and
collects confirmations, per constitution principle IV. A single WS wrapper
serves both the feed and confirmation responses (R5/R6).

**Alternatives considered**:
- **MUI / Ant Design** — rejected: heavier runtime dependency, themed
  defaults that fight a custom dashboard look.
- **A WS client library (e.g. socket.io)** — rejected: native WebSocket +
  our seq protocol is simpler and transport-agnostic; socket.io adds a
  matching server protocol we don't need.
- **GraphQL subscriptions** — rejected: overkill; WS + typed JSON events
  suffice (YAGNI).

---

## Summary of resolved unknowns

| ID | Unknown | Resolution |
|----|---------|------------|
| R1 | LLM provider abstraction | Thin `LlmProvider` protocol + OpenAI-compat & Anthropic adapters |
| R2 | MCP integration | Official `mcp` Python SDK, stdio + streamable_http, registry-wrapped |
| R3 | Skills | Manifest + callable/subprocess entry, same tool contract |
| R4 | Secret encryption | Fernet symmetric, master key from env |
| R5 | Realtime + reconnect | WebSocket + per-session seq IDs + persisted-event backfill |
| R6 | Confirmation protocol | WS round-trip, run blocks on Future, never auto-approve |
| R7 | Browser/computer sandbox | Playwright isolated profile; computer control in prepared sandbox |
| R8 | Cron | APScheduler + SQL jobstore; per-resource lock; runs over tool path |
| R9 | Frontend UI/WS | React+Vite+TS, shadcn/ui, native WS wrapper with backfill |

All NEEDS CLARIFICATION items resolved. No item remains for `/speckit-tasks`
to block on.
