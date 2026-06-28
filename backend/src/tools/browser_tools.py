"""Browser tools (T043, US5, research R7) — Playwright, isolated profiles.

browser_navigate / browser_click / browser_read, registered behind the tool
contract as `sensitive` (require confirmation via the gate). Profiles are
isolated per session; never the operator's personal profile (FR-017).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from src.config import get_settings
from src.models.db import db_session
from src.models.entities import BrowserComputerSession, SessionKind, SessionStatus, RiskLevel
from src.tools.registry import ToolDescriptor, register

logger = logging.getLogger(__name__)

# ponytail: one Playwright browser/page per session, lazily created.
_pages: dict[uuid.UUID, object] = {}
_browser: object | None = None


async def _get_page(session_id: uuid.UUID):
    """Return (or create) an isolated browser page for the session."""
    if session_id in _pages:
        return _pages[session_id]
    from playwright.async_api import async_playwright

    global _browser
    if _browser is None:
        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(headless=True)

    profile = Path(get_settings().browser_profile_root) / str(session_id)
    profile.mkdir(parents=True, exist_ok=True)
    context = await _browser.new_context(user_data_dir=str(profile))
    page = await context.new_page()

    # Record the sandboxed session.
    with db_session() as db:
        db.add(BrowserComputerSession(
            session_id=session_id, kind=SessionKind.browser,
            profile_dir=str(profile), status=SessionStatus.idle,
        ))
        db.commit()
    _pages[session_id] = page
    return page


async def _navigate(args: dict) -> dict:
    from src.tools.invoke import current_session_id

    sid = current_session_id.get()
    page = await _get_page(sid)
    await page.goto(args["url"])
    return {"url": args["url"], "title": await page.title()}


async def _click(args: dict) -> dict:
    from src.tools.invoke import current_session_id

    sid = current_session_id.get()
    page = await _get_page(sid)
    await page.click(args["selector"])
    return {"clicked": args["selector"]}


async def _read(args: dict) -> dict:
    from src.tools.invoke import current_session_id

    sid = current_session_id.get()
    page = await _get_page(sid)
    text = await page.inner_text("body")
    return {"text": text[:4000]}


def register_browser_tools() -> None:
    """Register browser tools as sensitive (confirmation-gated). session_id is
    injected by the invoke path via a closure in the agent loop's _invoke_tool.
    """
    # ponytail: browser tools need the session_id at exec time. The agent loop
    # calls invoke(name, args, session_id=...). invoke passes args only to the
    # executor; we close over session_id through invoke's kwargs is not possible
    # with the current registry signature. So we accept session_id via a
    # thread-local-ish module var set by the agent loop before each call.
    register(ToolDescriptor(
        name="browser_navigate", description="Navigate the browser to a URL.",
        source_type="browser",
        input_schema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
        risk_level=RiskLevel.sensitive, timeout_seconds=60,
    ), _navigate)
    register(ToolDescriptor(
        name="browser_click", description="Click an element by CSS selector.",
        source_type="browser",
        input_schema={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
        risk_level=RiskLevel.sensitive, timeout_seconds=30,
    ), _click)
    register(ToolDescriptor(
        name="browser_read", description="Read the visible text of the current page.",
        source_type="browser",
        input_schema={"type": "object"},
        risk_level=RiskLevel.sensitive, timeout_seconds=30,
    ), _read)
