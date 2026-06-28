// Typed HTTP API client (T023) — wraps contracts/http-api.md.
// All calls send the session cookie; backend owns auth/secrets.

export interface Provider {
  id: string;
  name: string;
  type: "openai_compatible" | "anthropic";
  base_url: string;
}

export interface Model {
  id: string;
  provider_id: string;
  model_name: string;
  display_name: string;
  enabled: boolean;
}

export interface Session {
  id: string;
  model_id: string;
  title: string | null;
  created_at: string;
}

export interface ToolDescriptor {
  name: string;
  description: string;
  source_type: string;
  input_schema: object;
  risk_level: "none" | "sensitive" | "destructive";
  auto_run: boolean;
  timeout_seconds: number;
}

export interface ActivityEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
}

export interface Job {
  id: string;
  cron_expr: string;
  target_type: "tool" | "chat";
  target_ref: Record<string, unknown>;
  max_retries: number;
  status: "active" | "paused" | "failed";
  last_run_at: string | null;
  last_run_status: string | null;
  next_run_at: string | null;
}

const base = "";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(base + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.error?.message ?? `request failed: ${res.status}`);
  }
  return data as T;
}

export const api = {
  // auth
  register: (email: string, password: string) =>
    req<{ user_id: string }>("POST", "/api/auth/register", { email, password }),
  login: (email: string, password: string) =>
    req<{ ok: boolean }>("POST", "/api/auth/login", { email, password }),
  logout: () => req<{ ok: boolean }>("POST", "/api/auth/logout"),

  // llm
  listProviders: () => req<Provider[]>("GET", "/api/llm/providers"),
  createProvider: (p: { name: string; type: string; base_url: string; api_key: string }) =>
    req<Provider>("POST", "/api/llm/providers", p),
  deleteProvider: (id: string) => req<{ ok: boolean }>("DELETE", `/api/llm/providers/${id}`),
  listModels: (enabled?: boolean) =>
    req<Model[]>("GET", `/api/llm/models${enabled !== undefined ? `?enabled=${enabled}` : ""}`),
  createModel: (m: { provider_id: string; model_name: string; display_name: string }) =>
    req<Model>("POST", "/api/llm/models", m),
  toggleModel: (id: string, enabled: boolean) =>
    req<Model>("PATCH", `/api/llm/models/${id}`, { enabled }),

  // sessions
  listSessions: () => req<Session[]>("GET", "/api/sessions"),
  createSession: (model_id: string, title?: string) =>
    req<{ id: string }>("POST", "/api/sessions", { model_id, title }),
  getSession: (id: string) => req<Session & { messages: unknown[] }>("GET", `/api/sessions/${id}`),
  deleteSession: (id: string) => req<{ ok: boolean }>("DELETE", `/api/sessions/${id}`),
  getActivity: (id: string, sinceSeq = 0) =>
    req<ActivityEvent[]>("GET", `/api/sessions/${id}/activity?since_seq=${sinceSeq}`),

  // tools
  listTools: () => req<ToolDescriptor[]>("GET", "/api/tools"),

  // jobs
  listJobs: () => req<Job[]>("GET", "/api/jobs"),
  createJob: (j: { cron_expr: string; target_type: "tool" | "chat"; target_ref: object; max_retries?: number }) =>
    req<Job>("POST", "/api/jobs", j),
  patchJob: (id: string, status: "active" | "paused" | "failed") =>
    req<Job>("PATCH", `/api/jobs/${id}`, { status }),
  deleteJob: (id: string) => req<{ ok: boolean }>("DELETE", `/api/jobs/${id}`),
};
