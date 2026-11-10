import { createRoot } from "react-dom/client";
import ThesisCardMount from "./ThesisCardMount.jsx";
import { ensureDemoQueryFromLegacy } from "./demoScenario.js";
import "./thesis-card.css";

if (typeof window !== "undefined" && ensureDemoQueryFromLegacy()) {
  /* redirecting; do not mount */
} else {
  const rootEl = document.getElementById("thesis-card-root");
  if (rootEl) {
    createRoot(rootEl).render(<ThesisCardMount />);
  }
}
