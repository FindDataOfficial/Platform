// Confirmation prompt (T046, US5) — render pending confirmation_request events,
// send approve/decline over the WS. Constitution III: never auto-approve.
import { ActivityMessage } from "../services/ws";

export function ConfirmationPrompt({
  pending,
  onDecide,
}: {
  pending: ActivityMessage[];
  onDecide: (confirmationId: string, approved: boolean) => void;
}) {
  if (pending.length === 0) return null;
  const m = pending[0];
  const p = m.event.payload as Record<string, unknown>;
  const cid = p.confirmation_id as string;
  return (
    <div className="border-2 border-orange-400 bg-orange-50 p-3 m-2 rounded">
      <div className="font-semibold text-orange-800">
        ⚠️ Confirmation required ({String(p.risk_level)})
      </div>
      <div className="font-mono text-sm my-1">{String(p.action_summary)}</div>
      <div className="flex gap-2">
        <button
          onClick={() => onDecide(cid, true)}
          className="bg-green-600 text-white px-3 py-1 rounded text-sm"
        >
          Approve
        </button>
        <button
          onClick={() => onDecide(cid, false)}
          className="bg-red-600 text-white px-3 py-1 rounded text-sm"
        >
          Decline
        </button>
      </div>
    </div>
  );
}
