# Operator Runbook — Agent Platform

Provisioning and operational tasks. Implementation detail lives in the codebase;
this is the run-level guide.

## 1. First-time setup

```bash
cd backend
pip install -e ".[dev]"
playwright install chromium          # browser tools (T043)
export DATABASE_URL="sqlite:///./agent.db"          # dev; postgres for prod
export AGENT_PLATFORM_SECRET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
alembic upgrade head                  # prod; dev auto-creates tables on startup
uvicorn src.main:app --reload
```

Frontend:
```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## 2. Secret management (research R4)

- LLM provider API keys are encrypted at rest with Fernet (master key =
  `AGENT_PLATFORM_SECRET_KEY`).
- **Never** commit the master key. Rotate by: decrypt all provider keys with the
  old key, set the new env var, re-encrypt and re-save each provider's API key
  via `PATCH /api/llm/providers/{id}` with `{api_key}`.
- No endpoint ever returns `api_key` or its ciphertext (FR-018/020).

## 3. Sandboxed browser/computer control (research R7)

- Browser profiles live under `BROWSER_PROFILE_ROOT` (default
  `/tmp/agent-platform-profiles`), isolated per chat session — never the
  operator's personal profile.
- Computer control targets the prepared sandbox only. To allow control of the
  operator desktop, the operator must explicitly opt in per session (FR-017).
- For untrusted work, provision a container/VM as the sandbox; the in-process
  isolated-profile model is the v1 minimum.

## 4. Skills (research R3)

Drop a skill directory under `SKILLS_DIR` (default `skills/`) with a
`skill.json` manifest:

```json
{
  "name": "upper",
  "description": "Uppercase the input text",
  "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
  "risk_level": "none",
  "entry": ["python", "run.py"]
}
```

`entry` is either `["python", "run.py"]` (subprocess; receives args as JSON on
stdin, returns JSON on stdout) or `"module:function"` (Python callable). Restart
the backend to load.

## 5. MCP servers (research R2)

MCP servers are registered at runtime (wrap via `src.tools.mcp_adapter`). Each
remote tool is exposed behind the uniform tool contract as
`mcp_{server_id}_{tool_name}`. stdio and streamable_http transports are
supported.

## 6. Cron jobs (research R8)

Scheduled jobs persist to the SQL jobstore and survive restarts. Create via the
dashboard (`/#/jobs`) or `POST /api/jobs`. Jobs targeting the same browser/
computer session are serialized; an overlapping job gets `resource_busy`.

## 7. Trust boundaries (constitution III)

- Sensitive and destructive actions require explicit dashboard confirmation.
- Destructive actions can NEVER be set to auto-run (enforced at registration).
- All confirmation decisions are audit-logged (`src/api/audit.py`, FR-012).

## 8. Validation

Run the contract/unit suite (note: disable the environment's logfire/asyncio/
anyio/typeguard pytest plugins which conflict with Starlette's TestClient):

```bash
cd backend
AGENT_PLATFORM_SECRET_KEY=test python -m pytest tests/ \
  -p no:logfire -p no:cacheprovider -p no:asyncio -p no:anyio -p no:typeguard
```

Live WS smoke (bypasses pytest's WS transport):

```bash
AGENT_PLATFORM_SECRET_KEY=test PYTHONPATH=backend python backend/scripts/smoke_ws.py
```

End-to-end manual validation scenarios: see `specs/001-agent-platform/quickstart.md` (V1–V6).
