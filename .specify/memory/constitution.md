<!--
  ============================================================
  Sync Impact Report
  ============================================================
  Version change: [CONSTITUTION_VERSION] (unfilled template) → 1.0.0
  Type: Initial ratification (template → concrete). Treated as 1.0.0
        since no prior semantic version existed.

  Modified principles:
    - [PRINCIPLE_1_NAME] → I. Tool-First Architecture
    - [PRINCIPLE_2_NAME] → II. Live Observability (NON-NEGOTIABLE)
    - [PRINCIPLE_3_NAME] → III. Human-in-the-Loop at Trust Boundaries (NON-NEGOTIABLE)
    - [PRINCIPLE_4_NAME] → IV. React + Python Boundary
    - [PRINCIPLE_5_NAME] → V. Simplicity (YAGNI)

  Added sections:
    - Technology & Constraints (replaces [SECTION_2_NAME] placeholder)
    - Development Workflow (replaces [SECTION_3_NAME] placeholder)
    - Governance (concrete amendment + versioning + review policy)

  Removed sections: none

  Templates requiring updates:
    - .specify/templates/plan-template.md     ✅ reviewed — Constitution
      Check section reads gates from this file; no edit needed.
    - .specify/templates/spec-template.md     ✅ reviewed — generic,
      no constitution-coupled slots; no edit needed.
    - .specify/templates/tasks-template.md    ✅ reviewed — generic
      phase/user-story structure; no edit needed.
    - .specify/templates/commands/            ⚠ N/A — directory absent.

  Follow-up TODOs: none. All placeholders resolved.
  ============================================================
-->

# PaaS Agent Platform Constitution

## Core Principles

### I. Tool-First Architecture

Every capability the agent can exercise — MCP servers, skills, cron jobs,
browser actions, and computer control — MUST be registered as a tool behind
one uniform invoke contract (name, input schema, execution, structured
result). Agents act ONLY through tools; there is no ad-hoc capability code
bypassing the registry.

- A capability that cannot be expressed as a tool does not ship.
- Tools are discoverable and self-describing (schema + description).
- Cron is a scheduler over tools, not a separate execution path.

### II. Live Observability (NON-NEGOTIABLE)

All agent actions emit structured activity events streamed to the dashboard
in real time over a persistent channel (WebSocket). The user MUST see what
the agent is doing as it does it: tool calls, inputs, results, reasoning
steps, and errors.

- Silent or fire-and-forget execution is forbidden for agent-driven work.
- Events are the single source of truth for the dashboard's activity feed.
- Long-running actions stream progress, not just a final result.

### III. Human-in-the-Loop at Trust Boundaries (NON-NEGOTIABLE)

Browser and computer control, and any mutating, network-side, or otherwise
sensitive action, require explicit user confirmation by default. Destructive
operations NEVER auto-execute.

- Confirmation is the default; auto-run is an explicit, auditable opt-in per
  tool/action class.
- Browser and computer-control sessions are sandboxed and scoped to least
  privilege.
- Every trust-boundary decision is logged with actor, target, and outcome.

### IV. React + Python Boundary

The frontend is React + TypeScript; the backend is Python 3.11+ (FastAPI).
They communicate exclusively over a typed HTTP/WebSocket contract. There is
no shared runtime, no shared in-memory state, and no business logic on the
frontend beyond presentation and input capture.

- The contract is the seam; changes there are versioned and reviewed first.
- Backend owns all tool execution, scheduling, persistence, and secrets.
- Frontend renders activity and collects confirmation, nothing more.

### V. Simplicity (YAGNI)

Start with the minimum that works. Stdlib and native platform features
before new dependencies. No speculative abstraction, no interface with one
implementation, no scaffolding "for later."

- Two stdlib options of equal size: pick the one correct on edge cases.
- Add a dependency only when a few lines genuinely cannot do it.
- A deliberate shortcut carries a `ponytail:` comment naming its ceiling
  and upgrade path.

## Technology & Constraints

- **Frontend**: React + TypeScript (Vite). Dashboard renders streamed
  activity and surfaces confirmation prompts.
- **Backend**: Python 3.11+, FastAPI. Owns the tool registry, scheduler
  (cron), agent loop, and persistence.
- **Realtime**: WebSocket channel for activity streaming and confirmation
  round-trips.
- **Tool protocol**: MCP for external tool servers; internal tools conform
  to the same invoke contract.
- **Storage**: SQL (PostgreSQL in production; SQLite acceptable for local
  dev). Schema is migration-managed.
- **Capabilities**: Browser automation and computer control run in
  sandboxed sessions; never on the operator's primary desktop without an
  explicit opt-in.
- **Constraints**: Tool invocations are timeout-bounded; secrets never
  cross the contract to the frontend; PII/credential logging is prohibited.

## Development Workflow

- **Spec-first (SDD)**: speckit chain (specify → plan → tasks → implement)
  governs every feature. No implementation begins without a spec.md.
- **Tests at trust boundaries**: confirmation gates, tool-invoke contract,
  scheduling correctness, and sandbox isolation MUST have runnable checks.
  Non-trivial logic leaves behind at least one failing-then-passing check
  (assert-based self-check or a small focused test).
- **Constitution Check**: each plan runs a gate pass against these
  principles before research and again after design; violations require
  explicit justification recorded in the plan's Complexity Tracking.
- **Review**: PRs verify constitution compliance, contract-version
  discipline, and observability of any new agent action.

## Governance

This constitution supersedes all other practices for the PaaS Agent
Platform. It is the authority consulted by the speckit Constitution Check
gate in every plan.

- **Amendments**: require a documented change, a stated rationale, a
  migration/impact note for in-flight work, and a version bump.
- **Versioning**: semantic versioning. MAJOR for principle
  removal/redefinition (breaking governance); MINOR for a new principle or
  materially expanded guidance; PATCH for clarifications, wording, and
  typo fixes.
- **Compliance review**: every PR/plan must verify adherence; unjustified
  complexity or silent agent actions block merge. Use
  `.specify/memory/constitution.md` (this file) as the runtime reference.

**Version**: 1.0.0 | **Ratified**: 2026-06-28 | **Last Amended**: 2026-06-28
