import { createRoot } from "react-dom/client";
import "./thesis-card.css";

async function boot() {
  if (typeof window === "undefined") return;
  const rootEl = document.getElementById("thesis-card-root");
  if (!rootEl) return;

  const params = new URLSearchParams(window.location.search);
  if (params.has("preview")) {
    const { ensureDemoQueryFromLegacy } = await import("./demoScenario.js");
    if (ensureDemoQueryFromLegacy()) return;
  }

  if (params.has("demo")) {
    const { default: DemoThesisMount } = await import("./DemoThesisMount.jsx");
    createRoot(rootEl).render(<DemoThesisMount />);
    return;
  }

  const { default: LiveThesisMount } = await import("./LiveThesisMount.jsx");
  createRoot(rootEl).render(<LiveThesisMount />);
}

boot();
