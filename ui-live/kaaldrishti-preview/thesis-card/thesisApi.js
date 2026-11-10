export function thesisApiBase() {
  const g = typeof window !== "undefined" ? window.THESIS_API_BASE : "";
  return (g || "").replace(/\/$/, "");
}

function url(path) {
  return `${thesisApiBase()}${path}`;
}

export async function createTrade(body) {
  const res = await fetch(url("/trade"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`create trade ${res.status}`);
  return res.json();
}

export async function fetchTrade(tradeId) {
  const res = await fetch(url(`/trade/${tradeId}`), { cache: "no-store" });
  if (!res.ok) throw new Error(`trade ${res.status}`);
  return res.json();
}

export async function fetchState(tradeId) {
  const res = await fetch(url(`/trade/${tradeId}/state`), { cache: "no-store" });
  if (!res.ok) throw new Error(`state ${res.status}`);
  return res.json();
}

export async function fetchBook(tradeId) {
  const res = await fetch(url(`/trade/${tradeId}/book`), { cache: "no-store" });
  if (!res.ok) throw new Error(`book ${res.status}`);
  return res.json();
}

export function openStateStream(tradeId, { onState, onPing, onError }) {
  const base = thesisApiBase();
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = base
    ? new URL(base).host
    : window.location.host;
  const path = base ? new URL(base).pathname.replace(/\/$/, "") : "";
  const wsUrl = `${proto}//${host}${path}/trade/${tradeId}/stream`;

  const ws = new WebSocket(wsUrl);
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "ping") {
        onPing?.(data);
        return;
      }
      if (data.type && data.type !== "ping") onState(data);
      else if (data.state) onState({ ...data, type: "confirmed_state" });
    } catch (e) {
      onError?.(e);
    }
  };
  ws.onerror = (e) => onError?.(e);
  return () => ws.close();
}
