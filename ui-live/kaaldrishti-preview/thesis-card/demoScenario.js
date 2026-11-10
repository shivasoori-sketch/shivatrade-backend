/** Static fixtures for ?demo= on the public kaaldrishti slot (no API / trade lock). */

export const DEMO_BANNER =
  "DEMO — static fixtures, not live market data. Not a validation claim.";

const createdAt = () =>
  new Date(Date.now() - 47 * 60 * 1000 - 22 * 1000).toISOString();

const baseTrade = () => ({
  symbol: "NIFTY",
  direction: "long",
  entry_price: 24125,
  stop_loss: 24080,
  target: 24240,
  created_at: createdAt(),
});

export const DEMO_SCENARIOS = {
  holds: {
    trade: baseTrade(),
    state: {
      state: "HOLDS",
      decision_line: "HOLD",
      annotation: "observing: sweep suspected",
      data_stale: false,
      conditions: [
        { id: "vwap", label: "Price holds above session VWAP", met: true },
        { id: "book", label: "Book aligned with direction", met: true },
        { id: "structure", label: "No lower high on 5m", met: true },
      ],
    },
    book: { book_score: 72, divergence_flag: false, sweep_risk: false },
    timeInTradeLabel: "47:22",
    adversePts: "3.5",
  },
  weakening: {
    trade: baseTrade(),
    state: {
      state: "WEAKENING",
      decision_line: "REDUCE — book diverging",
      annotation: "",
      data_stale: false,
      conditions: [
        { id: "vwap", label: "Price holds above session VWAP", met: true },
        { id: "book", label: "Book aligned with direction", met: false },
        { id: "structure", label: "No lower high on 5m", met: true },
      ],
    },
    book: { book_score: 38, divergence_flag: true, sweep_risk: false },
    timeInTradeLabel: "1:12:08",
    adversePts: "11.0",
  },
  invalidated: {
    trade: baseTrade(),
    state: {
      state: "INVALIDATED",
      decision_line: "EXIT — core thesis broken",
      annotation: "",
      data_stale: false,
      conditions: [
        { id: "vwap", label: "Price holds above session VWAP", met: false },
        { id: "book", label: "Book aligned with direction", met: false },
        { id: "structure", label: "No lower high on 5m", met: false },
      ],
    },
    book: { book_score: 22, divergence_flag: true, sweep_risk: true },
    timeInTradeLabel: "0:18:44",
    adversePts: "24.5",
  },
};

const LEGACY_PREVIEW_MAP = {
  live: "holds",
  holds: "holds",
  weakening: "weakening",
  invalidated: "invalidated",
};

/** Redirect deprecated ?preview=… to ?demo=… (one-shot). */
export function ensureDemoQueryFromLegacy() {
  const params = new URLSearchParams(window.location.search);
  if (!params.has("preview")) return false;
  const mapped = LEGACY_PREVIEW_MAP[params.get("preview").toLowerCase()];
  params.delete("preview");
  params.delete("trade_id");
  if (mapped) params.set("demo", mapped);
  const q = params.toString();
  const next = q
    ? `${window.location.pathname}?${q}${window.location.hash || ""}`
    : `${window.location.pathname}${window.location.hash || ""}`;
  window.location.replace(next);
  return true;
}

export function demoModeFromPage() {
  const raw = new URLSearchParams(window.location.search).get("demo");
  if (!raw) return "";
  const key = raw.toLowerCase();
  return DEMO_SCENARIOS[key] ? key : "";
}

export function demoHref(mode = "holds") {
  const params = new URLSearchParams(window.location.search);
  params.set("demo", mode);
  params.delete("trade_id");
  params.delete("preview");
  return `?${params.toString()}`;
}

export function demoHoldsHref() {
  return demoHref("holds");
}

export function applyDemoNoIndex() {
  if (!demoModeFromPage()) return;
  let el = document.querySelector('meta[name="robots"]');
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute("name", "robots");
    document.head.appendChild(el);
  }
  el.setAttribute("content", "noindex, nofollow");
}
