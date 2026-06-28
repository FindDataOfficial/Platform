import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { Dashboard } from "./pages/Dashboard";
import { LlmManagement } from "./pages/LlmManagement";
import { ScheduledJobs } from "./pages/ScheduledJobs";

function Router() {
  const hash = window.location.hash;
  if (hash.startsWith("#/llm")) return <LlmManagement />;
  if (hash.startsWith("#/jobs")) return <ScheduledJobs />;
  return <Dashboard />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Router />
  </React.StrictMode>
);
