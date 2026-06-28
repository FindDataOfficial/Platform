// Scheduled jobs page (T039, US4) — create/list/pause cron jobs, view activity.
import { useEffect, useState } from "react";
import { api, Job } from "../services/api";

export function ScheduledJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [cron, setCron] = useState("* * * * *");
  const [toolName, setToolName] = useState("current_time");
  const [args, setArgs] = useState("{}");

  function refresh() {
    api.listJobs().then(setJobs).catch(() => {});
  }
  useEffect(refresh, []);

  function create() {
    let parsed = {};
    try { parsed = JSON.parse(args); } catch { alert("arguments must be valid JSON"); return; }
    api
      .createJob({ cron_expr: cron, target_type: "tool", target_ref: { type: "tool", tool_name: toolName, arguments: parsed } })
      .then(refresh);
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <a href="/" className="text-blue-600 text-sm">← Dashboard</a>
        <h1 className="text-2xl font-bold">Scheduled Jobs</h1>
      </div>

      <section className="space-y-2">
        <h2 className="font-semibold">New Job</h2>
        <div className="grid grid-cols-2 gap-2">
          <input placeholder="cron (* * * * *)" value={cron} onChange={(e) => setCron(e.target.value)} className="border p-1 rounded" />
          <input placeholder="tool name" value={toolName} onChange={(e) => setToolName(e.target.value)} className="border p-1 rounded" />
          <input placeholder='arguments JSON, e.g. {}' value={args} onChange={(e) => setArgs(e.target.value)} className="border p-1 rounded col-span-2 font-mono" />
          <button onClick={create} className="bg-blue-600 text-white rounded p-1 col-span-2">Create Job</button>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">Jobs</h2>
        {jobs.map((j) => (
          <div key={j.id} className="border rounded p-2">
            <div className="flex justify-between">
              <span className="font-mono text-sm">{j.cron_expr} → {j.target_type}</span>
              <span className="text-xs">{j.status} · last: {j.last_run_status ?? "—"}</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">next: {j.next_run_at ?? "—"}</div>
            <div className="flex gap-2 mt-1">
              {j.status === "active" ? (
                <button onClick={() => api.patchJob(j.id, "paused").then(refresh)} className="text-orange-600 text-sm">pause</button>
              ) : (
                <button onClick={() => api.patchJob(j.id, "active").then(refresh)} className="text-green-600 text-sm">resume</button>
              )}
              <button onClick={() => api.deleteJob(j.id).then(refresh)} className="text-red-600 text-sm">delete</button>
            </div>
          </div>
        ))}
        {jobs.length === 0 && <p className="text-gray-400 text-sm">No jobs yet.</p>}
      </section>
    </div>
  );
}
