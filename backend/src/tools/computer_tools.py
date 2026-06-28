"""Computer-control tools (T044, US5, research R7).

mouse / keyboard / screen tools, scoped to the prepared sandbox — never the
operator's primary desktop unless explicit per-session opt-in (FR-009/FR-017).
Registered as `destructive` (always confirmation-gated, never auto-run).

v1 uses Playwright's input where available and pynput-style stubs otherwise;
the sandbox boundary is enforced by the operator's runbook provisioning.
"""

from __future__ import annotations

from src.models.entities import RiskLevel
from src.tools.registry import ToolDescriptor, register


async def _type_text(args: dict) -> dict:
    # ponytail: route text input through the active browser page when present;
    # upgrade to a real OS-level driver (pynput) when computer-only sessions ship.
    from src.tools.browser_tools import _pages
    from src.tools.invoke import current_session_id

    sid = current_session_id.get()
    page = _pages.get(sid) if sid else None
    if page is not None:
        await page.keyboard.type(args["text"])
        return {"typed_via": "browser", "chars": len(args["text"])}
    return {"typed_via": "noop", "chars": len(args["text"]), "note": "no active browser session"}


async def _screenshot(args: dict) -> dict:
    from src.tools.browser_tools import _pages
    from src.tools.invoke import current_session_id

    sid = current_session_id.get()
    page = _pages.get(sid) if sid else None
    if page is None:
        return {"note": "no active browser session to screenshot"}
    png = await page.screenshot()
    return {"bytes": len(png), "note": "screenshot captured (browser)"}


def register_computer_tools() -> None:
    register(ToolDescriptor(
        name="computer_type", description="Type text via keyboard (sandboxed).",
        source_type="computer",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        risk_level=RiskLevel.destructive,  # FR-011: always confirm, never auto-run
        timeout_seconds=30,
    ), _type_text)
    register(ToolDescriptor(
        name="computer_screenshot", description="Capture a screenshot of the sandboxed session.",
        source_type="computer",
        input_schema={"type": "object"},
        risk_level=RiskLevel.sensitive,
        timeout_seconds=30,
    ), _screenshot)
