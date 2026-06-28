# Feature Specification: Agent Platform

**Feature Branch**: `001-agent-platform`

**Created**: 2026-06-28

**Status**: Draft

**Input**: User description: "I want to create a platform that can use mcp, skills and cron. i also want to have ability to use the browser and computer like openclaw, i want to chat with ai in a dashboard, and it will show what does it doing"

## User Scenarios & Testing *(mandatory)*

<!--
  User stories ordered by importance. Each is independently testable and
  delivers value as a standalone MVP slice.
-->

### User Story 1 - Chat with AI and Watch It Work (Priority: P1)

A user opens the dashboard, types a request into the chat, and the AI
responds while the dashboard shows exactly what it is doing in real time —
each tool call, the inputs it used, the result it got back, its reasoning,
and any errors. The user always knows what the agent is doing as it does it.

**Why this priority**: This is the core loop. Without a chat surface that
streams live activity, none of the other capabilities have anywhere to be
seen or controlled. It is the minimum that makes the platform useful.

**Independent Test**: Send a chat message that requires one tool call (e.g.
"what time is it in Tokyo" via a tool). The dashboard renders the user
message, the assistant's reasoning, the tool call, its result, and the final
answer — all appearing live as they happen.

**Acceptance Scenarios**:

1. **Given** the dashboard is open, **When** the user sends a chat message,
   **Then** the message appears immediately and the assistant begins
   responding with activity events streamed in real time.
2. **Given** the agent decides to use a tool, **When** the tool is invoked,
   **Then** the dashboard shows the tool name, its inputs, and (once
   complete) its structured result before the assistant continues.
3. **Given** a tool invocation errors, **When** the error occurs, **Then**
   the dashboard surfaces the error in the activity feed and the assistant
   explains the failure rather than silently failing.
4. **Given** a long-running action is in progress, **When** the user is
   watching, **Then** progress events stream incrementally rather than the
   feed going silent until completion.

---

### User Story 2 - Manage LLM Providers and Models (Priority: P2)

An operator can register LLM providers and the models they offer, store the
provider API credentials securely, choose which model a chat session or
scheduled job uses, and enable or disable models. The agent then runs
against the selected model, and each LLM call's model, token usage, and cost
are visible in the activity feed.

**Why this priority**: The agent cannot run without a configured model.
LLM management is the config layer that makes the chat loop (P1) and every
downstream capability actually function; it belongs ahead of tools and
scheduling.

**Independent Test**: Register one LLM provider with a valid API key, enable
one of its models, start a chat session selecting that model, and send a
message. Verify the assistant responds and the activity feed shows the model
used and token usage for the call.

**Acceptance Scenarios**:

1. **Given** the operator has a provider endpoint and API key, **When** they
   register the LLM provider, **Then** its models become available to
   select for sessions and jobs.
2. **Given** an API credential is stored, **When** it is saved, **Then** it
   is kept as a backend secret and never transmitted to or displayed in the
   frontend.
3. **Given** multiple models are registered, **When** the user starts a
   session or job, **Then** they can select which enabled model to use.
4. **Given** a model is disabled, **When** the agent lists available models,
   **Then** the disabled model is not offered.
5. **Given** an LLM call completes, **When** the result streams, **Then**
   the activity feed shows the model, token usage, and cost for that call.

---

### User Story 3 - Run Tools via MCP and Skills (Priority: P3)

A user (or the AI on their behalf) can exercise registered tools — both
external MCP tool servers and locally-defined skills — to accomplish tasks.
Tools are discoverable and self-describing: the AI can see what tools exist
and what each accepts, and invoke them through one consistent interface.

**Why this priority**: Tools are the platform's hands. Chat (P1) without
tools is just an LLM wrapper; adding MCP + skills makes the agent able to
actually do things on the user's behalf.

**Independent Test**: Register one MCP server and one skill. Ask the agent
to perform a task requiring each. Verify the dashboard shows the correct
tool being selected and invoked with valid inputs, and the result returned.

**Acceptance Scenarios**:

1. **Given** an MCP tool server is registered, **When** the agent needs that
   capability, **Then** it invokes the MCP tool through the shared tool
   contract and the result appears in the activity feed.
2. **Given** a skill is registered, **When** the agent determines the skill
   applies, **Then** it invokes the skill through the same contract as MCP
   tools.
3. **Given** tools are registered, **When** the agent lists available
   capabilities, **Then** each tool's name and input schema are visible and
   accurate.
4. **Given** a tool is invoked with invalid input, **When** validation
   fails, **Then** the error is reported to the agent and surfaced in the
   feed without crashing the session.

---

### User Story 4 - Schedule Recurring Tasks with Cron (Priority: P4)

A user can schedule a tool or a chat instruction to run on a recurring
schedule (cron). Scheduled jobs run automatically at their times, and every
run appears in the activity feed just like an interactive session.

**Why this priority**: Scheduling turns the platform from a reactive chat
tool into an autonomous worker. It depends on P3 (tools must exist to be
scheduled) and P1 (runs must be observable).

**Independent Test**: Create a cron job that invokes a tool every minute.
Wait two minutes and confirm two runs appear in the activity feed with
their tool calls and results.

**Acceptance Scenarios**:

1. **Given** the user defines a cron schedule for a tool, **When** the
   scheduled time arrives, **Then** the job runs automatically without the
   user being present.
2. **Given** a scheduled job runs, **When** it executes, **Then** its
   activity is streamed/recorded in the same feed as interactive sessions.
3. **Given** a scheduled job fails, **When** the next scheduled time
   arrives, **Then** the job retries according to its policy and the failure
   is visible in the feed.
4. **Given** the user lists scheduled jobs, **When** they view the list,
   **Then** each job shows its schedule, target tool, last-run status, and
   next-run time.

---

### User Story 5 - Browser and Computer Control with Confirmation (Priority: P5)

A user can direct the AI to act in a browser (navigate, click, read pages)
and on the computer (mouse, keyboard, screen) like an agentic computer-use
tool. Because these actions are sensitive, the dashboard asks the user to
confirm before the agent executes them; nothing destructive runs
automatically.

**Why this priority**: Computer/browser control is the highest-power and
highest-risk capability. It must come after the safer loop (chat, tools,
scheduling) is solid and the confirmation system exists.

**Independent Test**: Ask the agent to open a browser and navigate to a
URL. Confirm the dashboard prompts for approval, approve it, and watch the
browser action stream its steps live in the feed.

**Acceptance Scenarios**:

1. **Given** the agent proposes a browser or computer action, **When** the
   action reaches a trust boundary, **Then** the dashboard presents a
   confirmation prompt and the agent waits for approval before executing.
2. **Given** the user approves a browser action, **When** it executes,
   **Then** each step (navigate, click, read) streams to the activity feed
   in real time.
3. **Given** the user declines a proposed action, **When** the agent
   receives the rejection, **Then** it does not execute and reports the
   decline in the feed.
4. **Given** a destructive action is proposed (e.g. deleting a file,
   submitting a form that spends money), **When** it reaches the boundary,
   **Then** it requires explicit confirmation and never auto-executes.

---

### Edge Cases

- What happens when an MCP tool server is unreachable or times out mid-call?
  The agent must report the failure in the feed and not hang the session;
  the user can retry or pick an alternative.
- What happens when two scheduled cron jobs fire at the same instant and
  both try to control the same browser session? The system must serialize or
  reject the conflict rather than producing undefined behavior.
- What happens when the WebSocket drops during an agent run? The backend
  must continue the run and the dashboard must reconnect and backfill missed
  activity rather than losing or duplicating events.
- What happens when a user closes the dashboard while a confirmation prompt
  is pending? The agent must hold (not auto-approve) and resume when the
  user returns.
- What happens when a skill or MCP tool is removed while a scheduled job
  references it? The job must fail clearly on next run rather than silently
  no-op.
- What happens when a registered LLM provider's API key is invalid, expired,
  or rate-limited? The system must report the failure clearly in the feed,
  fall back to an enabled alternative model if configured, and not silently
  retry in a hot loop.
- What happens when a model selected by a session or job is later disabled
  or removed by the operator? The session/job must surface a clear
  "model unavailable" error and prompt for a new selection rather than
  running against a stale configuration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a chat interface in a dashboard where the
  user converses with an AI assistant.
- **FR-002**: System MUST stream every agent action to the dashboard in real
  time, including reasoning, tool calls, inputs, results, and errors.
- **FR-003**: System MUST expose a single, uniform tool-invoke contract
  (name, input schema, execution, structured result) through which the agent
  exercises ALL capabilities.
- **FR-004**: System MUST support registering and invoking external MCP tool
  servers through that contract.
- **FR-005**: System MUST support registering and invoking locally-defined
  skills through the same contract as MCP tools.
- **FR-006**: System MUST allow the user to schedule tool invocations on
  recurring cron schedules.
- **FR-007**: System MUST run scheduled jobs automatically at their
  scheduled times and surface their activity in the same feed as interactive
  sessions.
- **FR-008**: System MUST support browser automation (navigate, click, read
  page content) as agent tools.
- **FR-009**: System MUST support computer control (mouse, keyboard, screen
  interaction) as agent tools.
- **FR-010**: System MUST require explicit user confirmation before
  executing browser, computer-control, or otherwise sensitive actions;
  confirmation is the default, auto-run is an explicit opt-in per action
  class.
- **FR-011**: System MUST NEVER auto-execute destructive actions; they
  require explicit confirmation every time.
- **FR-012**: System MUST log every trust-boundary decision with actor,
  target, and outcome.
- **FR-013**: System MUST make tools discoverable and self-describing (name
  + input schema) so the agent and user can see available capabilities.
- **FR-014**: System MUST validate tool inputs against the tool's schema and
  report violations to the agent and feed without crashing the session.
- **FR-015**: System MUST persist chat sessions, scheduled jobs, and
  activity history so they survive page reloads and reconnection.
- **FR-016**: System MUST bound every tool invocation with a timeout and
  surface timeouts as errors in the feed.
- **FR-017**: System MUST run browser and computer-control sessions in a
  sandboxed, least-privilege scope.
- **FR-018**: System MUST keep secrets on the backend and never transmit
  them to the frontend across the contract.
- **FR-019**: System MUST allow registering LLM providers (endpoint + type)
  and the models they offer.
- **FR-020**: System MUST allow the operator to store and manage API
  credentials for LLM providers as backend secrets, never exposed to the
  frontend.
- **FR-021**: System MUST allow selecting which enabled LLM model a chat
  session or scheduled job uses.
- **FR-022**: System MUST allow enabling and disabling registered models so
  unavailable ones are not offered to the agent.
- **FR-023**: System MUST surface LLM call metadata (model, token usage,
  cost) in the activity feed for each assistant response.
- **FR-024**: System MUST handle LLM provider failures (invalid/expired
  credential, rate limit, model unavailable) by reporting the error in the
  feed and failing over to an enabled alternative model when one is
  configured.

### Key Entities *(include if feature involves data)*

- **Chat Session**: A conversation between a user and the assistant. Holds
  ordered messages and links to its activity history.
- **Message**: A single entry in a chat session (user, assistant, or system
  authored), with content and a timestamp.
- **Activity Event**: A structured record of one agent action (tool call,
  reasoning step, LLM call, error, confirmation request/result). The single
  source of truth for the dashboard feed; belongs to a session or scheduled
  run.
- **LLM Provider**: A registered model provider (endpoint + type). Holds the
  provider's API credential as a backend secret.
- **LLM Model**: A model offered by a provider, selectable per session or
  scheduled job. Has an enable/disable state and usage metadata (token
  counts, cost).
- **Tool**: A registered capability with a name, description, input schema,
  and type (MCP server, skill, built-in). The unit the agent invokes.
- **Skill**: A locally-defined, packaged agent capability invokable through
  the tool contract. A specialization of Tool.
- **MCP Server**: An external tool server registered with the platform and
  exposed as Tools. A specialization of Tool.
- **Scheduled Job (Cron)**: A recurring schedule targeting a tool or chat
  instruction. Holds cron expression, target, status, last-run, and
  next-run.
- **Confirmation Request**: A pending approval for a trust-boundary action,
  linking the proposed action to the user's approve/decline decision.
- **Browser/Computer Session**: A sandboxed execution context for browser
  automation or computer control, scoped to least privilege.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can send a chat message and see the assistant's first
  activity event within 2 seconds in normal conditions.
- **SC-002**: 100% of agent tool calls, inputs, results, and errors appear
  in the dashboard activity feed — no silent or unobserved agent actions.
- **SC-003**: Users can register an MCP server and a skill and successfully
  invoke each through the chat within a single session.
- **SC-003a**: An operator can register an LLM provider, enable a model, and
  run a chat session against it, with the model and token usage visible in
  the activity feed; stored credentials are never exposed to the frontend.
- **SC-004**: A scheduled cron job executes at its configured time with
  zero user interaction, with its run visible in the activity feed.
- **SC-005**: 100% of browser and computer-control actions require explicit
  user confirmation before executing; 0% of destructive actions
  auto-execute.
- **SC-006**: Users can reconnect after a dropped connection and see the
  complete activity history of an in-progress run with no lost or duplicated
  events.
- **SC-007**: A user with no prior training can understand what the agent is
  doing from the dashboard feed alone, validated by 80%+ of test users
  correctly describing the agent's current action.
- **SC-008**: The platform supports at least 10 concurrent active sessions
  without degradation of real-time activity streaming.

## Assumptions

- The platform is a self-hosted web application; the operator and end users
  access it via a browser on a desktop. Mobile is out of scope for v1.
- A single deployment serves a small team (tens of users) initially; large
  multi-tenant scale is a later concern.
- The AI model and its API are managed in-platform: the operator registers
  LLM providers, stores their API credentials as backend secrets, and
  enables the models the agent may use. The platform integrates with at
  least one model provider out of the box.
- The operator runs the backend on a machine or container where browser and
  computer-control sandboxes can be provisioned; control never targets the
  operator's primary desktop without an explicit opt-in.
- Authentication uses standard web session login; advanced SSO/RBAC is
  deferred beyond a basic authenticated-user model for v1.
- Cron scheduling uses standard 5-field cron expressions in the server's
  local timezone.
- Browser automation and computer control are scoped to a managed/sandboxed
  environment rather than arbitrary third-party machines.
- The contract between frontend and backend is typed and versioned; the
  backend owns all tool execution, scheduling, persistence, and secrets
  (per the project constitution).
