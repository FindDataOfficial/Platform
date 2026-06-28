"""Runnable live WS smoke check (US1, V1/SC-006) — bypasses pytest.

Uses a fake LLM provider so no network is needed. Proves the full live path:
connect → chat → 3 activity events stream with monotonic seqs → reconnect
backfills by seq with no loss/dup.

Run: AGENT_PLATFORM_SECRET_KEY=test python scripts/smoke_ws.py
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.llm import provider as provider_mod
from src.llm.provider import BaseProvider, LlmResult, LlmUsage
from src.main import app
from src.models.db import Base, engine
import src.models.entities  # noqa: F401


class _FakeProvider(BaseProvider):
    async def complete(self, messages, tools=None) -> LlmResult:
        return LlmResult(text="hello back", usage=LlmUsage(5, 3), cost_usd=0.001)


def main() -> None:
    provider_mod.build_provider = lambda p, m: _FakeProvider()
    Base.metadata.create_all(engine)

    with TestClient(app) as c:
        c.post("/api/auth/register", json={"email": "u@v.com", "password": "password123"})
        c.post("/api/auth/login", json={"email": "u@v.com", "password": "password123"})
        p = c.post(
            "/api/llm/providers",
            json={"name": "p", "type": "openai_compatible", "base_url": "http://x", "api_key": "k"},
        ).json()
        m = c.post(
            "/api/llm/models",
            json={"provider_id": p["id"], "model_name": "m", "display_name": "M"},
        ).json()
        sid = c.post("/api/sessions", json={"model_id": m["id"]}).json()["id"]

        with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
            ws.send_text(json.dumps({"type": "chat", "content": "hi"}))
            events = [ws.receive_json() for _ in range(3)]

        seqs = [e["seq"] for e in events]
        types = [e["event"]["type"] for e in events]
        assert seqs == sorted(seqs), f"seq not monotonic: {seqs}"
        assert seqs == [1, 2, 3], seqs
        assert "reasoning" in types and "llm_call" in types, types
        llm_ev = next(e for e in events if e["event"]["type"] == "llm_call")
        assert llm_ev["event"]["payload"]["prompt_tokens"] == 5
        assert llm_ev["event"]["payload"]["cost_usd"] == 0.001
        last_seen = seqs[-1]

        # Reconnect: backfill should replay nothing old; a new turn streams only new.
        with c.websocket_connect(f"/ws/sessions/{sid}?last_seen_seq={last_seen}") as ws2:
            ws2.send_text(json.dumps({"type": "chat", "content": "again"}))
            new = [ws2.receive_json() for _ in range(3)]
            new_seqs = [e["seq"] for e in new]
            assert all(s > last_seen for s in new_seqs), new_seqs
            assert len(set(new_seqs)) == len(new_seqs), "duplicate seqs"

    print("WS live smoke OK: 3 events streamed, seq monotonic, reconnect backfill correct")


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
