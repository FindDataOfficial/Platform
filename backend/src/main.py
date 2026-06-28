"""FastAPI app entrypoint (US1 wiring).

Wires auth, sessions, llm, tools routers + WebSocket realtime + error handlers.
On startup: create tables (dev) / run alembic (prod), schedule cron jobs (US4).
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api import auth, jobs, llm, sessions, tools
from src.api.auth import current_user
from src.api.errors import register_error_handlers
from src.models.db import Base, SessionLocal, engine, get_db
import src.models.entities  # noqa: F401
from src.realtime import ws as realtime_ws

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Platform")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(llm.router)
    app.include_router(sessions.router)
    app.include_router(tools.router)
    app.include_router(jobs.router)
    app.include_router(realtime_ws.router)

    # Attach db to request.state for WS auth; HTTP uses the get_db dependency.
    @app.middleware("http")
    async def _db_state(request: Request, call_next):
        request.state.db = SessionLocal()
        try:
            return await call_next(request)
        finally:
            request.state.db.close()

    @app.on_event("startup")
    def _startup() -> None:
        # ponytail: dev uses create_all; prod runs `alembic upgrade head`.
        Base.metadata.create_all(engine)
        from src.tools.builtins import register_builtins
        from src.tools.skills_loader import load_skills
        from src.tools.browser_tools import register_browser_tools
        from src.tools.computer_tools import register_computer_tools

        register_builtins()
        register_browser_tools()
        register_computer_tools()
        load_skills()  # no-op if skills dir absent
        from src.scheduler.engine import start_scheduler
        start_scheduler()  # re-registers active jobs from DB (FR-015)

    @app.get("/api/me")
    def me(user=Depends(current_user), db: Session = Depends(get_db)):
        return {"user_id": str(user.id), "email": user.email}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
