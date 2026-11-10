import { useCallback, useEffect, useRef, useState } from "react";
import ThesisCard from "./ThesisCard.jsx";
import {
  fetchBook,
  fetchState,
  fetchTrade,
  openStateStream,
} from "./thesisApi.js";

const STORAGE_KEY = "thesis_trade_id";

function tradeIdFromPage() {
  const params = new URLSearchParams(window.location.search);
  return params.get("trade_id") || sessionStorage.getItem(STORAGE_KEY) || "";
}

function formatDuration(ms) {
  if (ms < 0) return "0:00";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  if (h > 0) return `${h}:${String(m % 60).padStart(2, "0")}`;
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export default function ThesisCardMount() {
  const [tradeId, setTradeId] = useState(tradeIdFromPage);
  const [trade, setTrade] = useState(null);
  const [state, setState] = useState(null);
  const [book, setBook] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const displayedState = useRef(null);

  const refreshBookOnStateChange = useCallback(async (id) => {
    try {
      const b = await fetchBook(id);
      setBook(b);
    } catch {
      /* book may be absent until first tick */
    }
  }, []);

  useEffect(() => {
    if (!tradeId) return undefined;
    let cancelled = false;

    (async () => {
      try {
        const [t, s] = await Promise.all([fetchTrade(tradeId), fetchState(tradeId)]);
        if (cancelled) return;
        sessionStorage.setItem(STORAGE_KEY, tradeId);
        setTrade(t);
        setState(s);
        displayedState.current = s.state;
        setLastUpdated(Date.now());
        await refreshBookOnStateChange(tradeId);
      } catch {
        if (!cancelled) setTradeId("");
      }
    })();

    const closeWs = openStateStream(tradeId, {
      onState: async (payload) => {
        if (cancelled) return;
        try {
          const s = await fetchState(tradeId);
          if (cancelled) return;
          setState(s);
          displayedState.current = s.state;
        } catch {
          setState((prev) => ({
            ...prev,
            state: payload.state,
            reasons: payload.reasons,
            decision_line: payload.decision_line,
          }));
          displayedState.current = payload.state;
        }
        setLastUpdated(
          payload.timestamp ? payload.timestamp * 1000 : Date.now()
        );
        await refreshBookOnStateChange(tradeId);
      },
    });

    return () => {
      cancelled = true;
      closeWs();
    };
  }, [tradeId, refreshBookOnStateChange]);

  const idle = !tradeId;
  const createdMs = trade?.created_at ? Date.parse(trade.created_at) : null;
  const timeInTrade =
    createdMs && !Number.isNaN(createdMs)
      ? formatDuration(Date.now() - createdMs)
      : "—";

  return (
    <ThesisCard
      idle={idle}
      trade={trade}
      state={state}
      book={book}
      lastUpdated={lastUpdated}
      timeInTradeLabel={timeInTrade}
      adversePts="—"
    />
  );
}
