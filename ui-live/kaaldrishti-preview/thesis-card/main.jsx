import { createRoot } from "react-dom/client";
import ThesisCardMount from "./ThesisCardMount.jsx";
import "./thesis-card.css";

const rootEl = document.getElementById("thesis-card-root");
if (rootEl) {
  createRoot(rootEl).render(<ThesisCardMount />);
}
