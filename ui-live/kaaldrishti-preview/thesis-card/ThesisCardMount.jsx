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

function adversePts(trade, ltp) {
  if (!trade || ltp == null) return "—";
  const entry = Number(trade.entry_price);
  if (Number.isNaN(entry)) return "—";
  if (trade.direction === "short") {
    return String(Math.max(0, ltp - entry).toFixed(1));
  }
  return String(Math.max(0, entry - ltp).toFixed(1));
}

export default function ThesisCardMount() {
  const [tradeId, setTradeId] = useState(tradeIdFromPage);
  const [trade, setTrade] = useState(null);
  const [state, setState] = useState(null);
  const [book, setBook] = useState(null);
  const [badgeUpdated, setBadgeUpdated] = useState(null);
  const [timeInTradeLabel, setTimeInTradeLabel] = useState("—");
  const [adverse, setAdverse] = useState("—");
  const displayedVerdict = useRef(null);
  const lastLtp = useRef(null);

  const refreshBookOnCandleClose = useCallback(async (id) => {
    try {
      const b = await fetchBook(id);
      setBook(b);
    } catch {
      /* book may be absent until first candle-close event */
    }
  }, []);

  const applyConfirmedState = useCallback(
    async (payload) => {
      if (
        payload.type === "confirmed_state" ||
        payload.type === "immediate_invalidate"
      ) {
        try {
          const s = await fetchState(tradeId);
          setState(s);
          displayedVerdict.current = s.state;
        } catch {
          setState((prev) => ({
            ...prev,
            state: payload.state,
            reasons: payload.reasons,
            decision_line: payload.decision_line,
            annotation: payload.annotation || "",
            intermediate_signal: payload.intermediate_signal,
          }));
          displayedVerdict.current = payload.state;
        }
        setBadgeUpdated(
          payload.timestamp ? payload.timestamp * 1000 : Date.now()
        );
        await refreshBookOnCandleClose(tradeId);
      } else if (payload.type === "intermediate_signal") {
        setState((prev) => ({
          ...prev,
          annotation: payload.annotation || prev?.annotation,
          intermediate_signal: payload.intermediate_signal,
        }));
        await refreshBookOnCandleClose(tradeId);
      }
    },
    [tradeId, refreshBookOnCandleClose]
  );

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
        displayedVerdict.current = s.state;
        setBadgeUpdated(Date.now());
        await refreshBookOnCandleClose(tradeId);
      } catch {
        if (!cancelled) setTradeId("");
      }
    })();

    const closeWs = openStateStream(tradeId, {
      onState: (payload) => {
        if (!cancelled) applyConfirmedState(payload);
      },
    });

    return () => {
      cancelled = true;
      closeWs();
    };
  }, [tradeId, applyConfirmedState, refreshBookOnCandleClose]);

  useEffect(() => {
    if (!trade?.created_at) return undefined;
    const createdMs = Date.parse(trade.created_at);
    if (Number.isNaN(createdMs)) return undefined;
    const tick = () => {
      setTimeInTradeLabel(formatDuration(Date.now() - createdMs));
      if (lastLtp.current != null) {
        setAdverse(adversePts(trade, lastLtp.current));
      }
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [trade]);

  const idle = !tradeId;

  return (
    <ThesisCard
      idle={idle}
      trade={trade}
      state={state}
      book={book}
      lastUpdated={badgeUpdated}
      timeInTradeLabel={timeInTradeLabel}
      adversePts={adverse}
    />
  );
}
