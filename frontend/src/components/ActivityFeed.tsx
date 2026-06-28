// Activity feed (T021/T034) — renders streamed activity events by type.
import { ActivityMessage } from "../services/ws";

export function ActivityFeed({ events }: { events: ActivityMessage[] }) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-gray-50">
      {events.length === 0 && (
        <p className="text-gray-400 text-sm">No activity yet — send a message to start.</p>
      )}
      {events.map((m) => {
        const t = m.event.type;
        const p = m.event.payload as Record<string, unknown>;
        let body: React.ReactNode;
        if (t === "llm_call") {
          body = `🤖 ${p.model} · ${p.prompt_tokens}/${p.completion_tokens} tok${
            p.cost_usd ? ` · $${p.cost_usd}` : ""
          }`;
        } else if (t === "tool_call") {
          body = `🔧 ${p.name}(${JSON.stringify(p.arguments)})`;
        } else if (t === "tool_result") {
          body = `✅ ${(p.content as unknown[])?.[0] ?? ""}`;
        } else if (t === "error") {
          body = `❌ ${p.code}: ${p.message}`;
        } else if (t === "reasoning") {
          body = p.text ? `💬 ${p.text}` : "💭 thinking…";
        } else if (t === "confirmation_request") {
          body = `⚠️ confirm: ${p.action_summary} (${p.risk_level})`;
        } else {
          body = JSON.stringify(p);
        }
        return (
          <div key={m.seq} className="text-sm font-mono bg-white rounded p-2 shadow-sm border">
            <span className="text-gray-400 mr-2">#{m.seq}</span>
            {body}
          </div>
        );
      })}
    </div>
  );
}
