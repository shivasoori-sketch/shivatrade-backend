/** Static fixtures for ?preview= on the public kaaldrishti slot (no API / trade lock). */

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

export const PREVIEW_SCENARIOS = {
  live: {
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

export function previewModeFromPage() {
  const raw = new URLSearchParams(window.location.search).get("preview");
  if (!raw) return "";
  const key = raw.toLowerCase();
  if (key === "holds") return "live";
  return PREVIEW_SCENARIOS[key] ? key : "";
}

export function previewHref(mode = "live") {
  const params = new URLSearchParams(window.location.search);
  params.set("preview", mode);
  params.delete("trade_id");
  return `?${params.toString()}`;
}

export function previewLiveHref() {
  return previewHref("live");
}
