# Agent Platform Backend

FastAPI backend: tool registry, agent loop, LLM management, cron scheduling,
sandboxed browser/computer control, live activity streaming.

## Setup

```bash
cd backend
pip install -e ".[dev]"
playwright install chromium          # T006 — operator step for browser tools
alembic upgrade head                 # apply schema migrations
export DATABASE_URL="sqlite:///./agent.db"
export AGENT_PLATFORM_SECRET_KEY="<fernet-key>"   # see runbook (R4)
uvicorn src.main:app --reload
```

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
