// Dashboard (T021) — chat input + live activity feed + session/model selector.
import { useEffect, useRef, useState } from "react";
import { api, Model, Session } from "../services/api";
import { ActivityFeed } from "../components/ActivityFeed";
import { ConfirmationPrompt } from "../components/ConfirmationPrompt";
import { WsClient, ActivityMessage } from "../services/ws";

export function Dashboard() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [events, setEvents] = useState<ActivityMessage[]>([]);
  const [pending, setPending] = useState<ActivityMessage[]>([]);
  const [input, setInput] = useState("");
  const [newModel, setNewModel] = useState("");
  const wsRef = useRef<WsClient | null>(null);

  useEffect(() => {
    api.listSessions().then(setSessions).catch(() => {});
    api.listModels(true).then(setModels).catch(() => {});
  }, []);

  // Connect WS when active session changes.
  useEffect(() => {
    if (!activeId) return;
    wsRef.current?.close();
    setEvents([]);
    const ws = new WsClient(activeId);
    ws.onActivity((m) => {
      setEvents((prev) => [...prev, m]);
      if (m.event.type === "confirmation_request") setPending((prev) => [...prev, m]);
      if (m.event.type === "confirmation_result") {
        const cid = (m.event.payload as Record<string, unknown>).confirmation_id as string;
        setPending((prev) => prev.filter((p) => (p.event.payload as Record<string, unknown>).confirmation_id !== cid));
      }
    });
    // Backfill on open via the initial since_seq query param + GET.
    api.getActivity(activeId, 0).then((evs) =>
      setEvents(evs.map((e) => ({ type: "activity" as const, seq: e.seq, event: { type: e.type, payload: e.payload } })))
    ).catch(() => {});
    ws.connect();
    wsRef.current = ws;
    return () => ws.close();
  }, [activeId]);

  function createSession() {
    if (!newModel) return;
    api.createSession(newModel).then((s) => {
      setSessions((prev) => [...prev, { id: s.id, model_id: newModel, title: null, created_at: new Date().toISOString() }]);
      setActiveId(s.id);
    });
  }

  function send() {
    if (!input.trim() || !activeId) return;
    wsRef.current?.send({ type: "chat", content: input });
    setInput("");
  }

  function decide(confirmationId: string, approved: boolean) {
    wsRef.current?.send({ type: "confirmation", confirmation_id: confirmationId, decision: approved ? "approve" : "decline" });
  }

  return (
    <div className="flex h-screen">
      <aside className="w-64 bg-gray-900 text-white p-4 space-y-3 overflow-y-auto">
        <h1 className="font-bold text-lg">Agent Platform</h1>
        <a href="/#/llm" className="block text-sm text-blue-300 hover:underline">LLM Management</a>
        <a href="/#/jobs" className="block text-sm text-blue-300 hover:underline">Scheduled Jobs</a>
        <div className="border-t border-gray-700 pt-3">
          <select value={newModel} onChange={(e) => setNewModel(e.target.value)} className="w-full text-black p-1 rounded">
            <option value="">Select model…</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>{m.display_name}</option>
            ))}
          </select>
          <button onClick={createSession} className="mt-2 w-full bg-blue-600 rounded p-1 text-sm">New Session</button>
        </div>
        <div className="space-y-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveId(s.id)}
              className={`block w-full text-left text-sm p-1 rounded ${s.id === activeId ? "bg-gray-700" : "hover:bg-gray-800"}`}
            >
              {s.title || s.id.slice(0, 8)}
            </button>
          ))}
        </div>
      </aside>
      <main className="flex-1 flex flex-col">
        <ConfirmationPrompt pending={pending} onDecide={decide} />
        <ActivityFeed events={events} />
        <div className="border-t p-3 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Message the agent…"
            className="flex-1 border rounded p-2"
            disabled={!activeId}
          />
          <button onClick={send} className="bg-blue-600 text-white px-4 rounded" disabled={!activeId}>
            Send
          </button>
        </div>
      </main>
    </div>
  );
}
