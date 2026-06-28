// LLM management page (T027) — register providers/models, enable/disable.
// No api_key field ever displays (FR-018/020).
import { useEffect, useState } from "react";
import { api, Model, Provider } from "../services/api";

export function LlmManagement() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("openai_compatible");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("");
  const [display, setDisplay] = useState("");
  const [providerId, setProviderId] = useState("");

  function refresh() {
    api.listProviders().then(setProviders);
    api.listModels().then(setModels);
  }
  useEffect(refresh, []);

  function addProvider() {
    api.createProvider({ name, type, base_url: baseUrl, api_key: apiKey }).then(refresh);
    setName(""); setBaseUrl(""); setApiKey("");
  }
  function addModel() {
    if (!providerId) return;
    api.createModel({ provider_id: providerId, model_name: modelName, display_name: display }).then(refresh);
    setModelName(""); setDisplay("");
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <a href="/" className="text-blue-600 text-sm">← Dashboard</a>
        <h1 className="text-2xl font-bold">LLM Management</h1>
      </div>

      <section className="space-y-2">
        <h2 className="font-semibold">Providers</h2>
        {providers.map((p) => (
          <div key={p.id} className="border rounded p-2 flex justify-between">
            <span>{p.name} · {p.type} · {p.base_url}</span>
            <button onClick={() => api.deleteProvider(p.id).then(refresh)} className="text-red-600 text-sm">delete</button>
          </div>
        ))}
        <div className="grid grid-cols-2 gap-2">
          <input placeholder="name" value={name} onChange={(e) => setName(e.target.value)} className="border p-1 rounded" />
          <select value={type} onChange={(e) => setType(e.target.value)} className="border p-1 rounded">
            <option value="openai_compatible">openai_compatible</option>
            <option value="anthropic">anthropic</option>
          </select>
          <input placeholder="base_url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} className="border p-1 rounded col-span-2" />
          <input placeholder="api key (stored encrypted, never shown)" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} className="border p-1 rounded col-span-2" />
          <button onClick={addProvider} className="bg-blue-600 text-white rounded p-1 col-span-2">Add Provider</button>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">Models</h2>
        {models.map((m) => (
          <div key={m.id} className="border rounded p-2 flex justify-between">
            <span>{m.display_name} ({m.model_name}) · {m.enabled ? "enabled" : "disabled"}</span>
            <button onClick={() => api.toggleModel(m.id, !m.enabled).then(refresh)} className="text-blue-600 text-sm">
              {m.enabled ? "disable" : "enable"}
            </button>
          </div>
        ))}
        <div className="grid grid-cols-2 gap-2">
          <select value={providerId} onChange={(e) => setProviderId(e.target.value)} className="border p-1 rounded col-span-2">
            <option value="">Select provider…</option>
            {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <input placeholder="model_name" value={modelName} onChange={(e) => setModelName(e.target.value)} className="border p-1 rounded" />
          <input placeholder="display_name" value={display} onChange={(e) => setDisplay(e.target.value)} className="border p-1 rounded" />
          <button onClick={addModel} className="bg-blue-600 text-white rounded p-1 col-span-2">Add Model</button>
        </div>
      </section>
    </div>
  );
}
