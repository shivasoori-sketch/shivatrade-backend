#!/usr/bin/env python3
"""Unified Upstox REST + WebSocket V3 client (shadow migration; token file only)."""

from __future__ import annotations

import json
import logging
import ssl
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

try:
    from google.protobuf.json_format import MessageToDict
    import MarketDataFeedV3_pb2 as _pb
except ImportError:  # pragma: no cover
    _pb = None
    MessageToDict = None

TOKEN_FILE = "/opt/shivtrade/shared/state/upstox_token.txt"
REST_BASE = "https://api.upstox.com"
AUTHORIZE_URL = f"{REST_BASE}/v3/feed/market-data-feed/authorize"
IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


class UpstoxConfigError(RuntimeError):
    pass


def load_token() -> str:
    path = Path(TOKEN_FILE)
    if not path.is_file():
        raise UpstoxConfigError(f"Upstox token missing at {TOKEN_FILE}")
    token = path.read_text(encoding="utf-8").strip()
    if not token or token.startswith("PASTE_"):
        raise UpstoxConfigError(f"Upstox token not configured in {TOKEN_FILE}")
    return token


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }


class UpstoxRestClient:
    def __init__(self, token: str | None = None, *, timeout: float = 45.0) -> None:
        self._token = token or load_token()
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(auth_headers(self._token))

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{REST_BASE}{path}"
        response = self._session.get(url, params=params or {}, timeout=self._timeout)
        if response.status_code >= 400:
            body = response.text[:400]
            raise RuntimeError(f"HTTP {response.status_code} {path}: {body}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected JSON from {path}")
        return payload

    def get_market_quote(self, instrument_keys: list[str]) -> dict[str, Any]:
        keys = ",".join(instrument_keys)
        return self.get(
            "/v2/market-quote/quotes",
            params={"instrument_key": keys},
        )

    def resolve_nearest_future(self, index_key: str) -> dict[str, Any]:
        underlying = {
            "NSE_INDEX|Nifty 50": ("NIFTY", "NSE"),
            "NSE_INDEX|Nifty Bank": ("BANKNIFTY", "NSE"),
            "BSE_INDEX|SENSEX": ("SENSEX", "BSE"),
        }.get(index_key)
        if not underlying:
            raise RuntimeError(f"Unsupported index_key {index_key}")
        query, exchange = underlying
        payload = self.get(
            "/v2/instruments/search",
            params={
                "query": query,
                "exchange": exchange,
                "segment": "FO",
                "expiry": "current_month",
            },
        )
        rows = payload.get("data") or []
        futs = [
            r
            for r in rows
            if str(r.get("instrument_type", "")).upper() == "FUT"
            and str(r.get("underlying_key") or "") == index_key
        ]
        if not futs:
            futs = [
                r
                for r in rows
                if str(r.get("instrument_type", "")).upper() == "FUT"
                and str(r.get("name") or "").upper() == query
            ]
        futs.sort(key=lambda r: str(r.get("expiry", "")))
        if not futs:
            raise RuntimeError(f"No FUT contract for {index_key}")
        return futs[0]

    def authorize_ws_v3(self) -> str:
        payload = self.get(AUTHORIZE_URL.replace(REST_BASE, ""))
        data = payload.get("data") or {}
        uri = data.get("authorizedRedirectUri") or data.get("authorized_redirect_uri")
        if not uri:
            raise RuntimeError("authorize response missing authorizedRedirectUri")
        return str(uri)


def decode_feed_message(raw: bytes | str) -> dict[str, Any] | None:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"type": "text", "payload": raw}
    if _pb is None or MessageToDict is None:
        raise RuntimeError("protobuf decoder unavailable; install upstox-python-sdk")
    feed = _pb.FeedResponse()
    feed.ParseFromString(raw)
    return MessageToDict(feed, preserving_proto_field_name=True)


def ist_now() -> datetime:
    return datetime.now(IST)


def parse_upstox_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Upstox full feed often uses epoch ms in LTPC paths
        secs = float(value)
        if secs > 1e12:
            secs /= 1000.0
        return datetime.fromtimestamp(secs, tz=IST)
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.isdigit():
            secs = float(text)
            if secs > 1e12:
                secs /= 1000.0
            return datetime.fromtimestamp(secs, tz=IST)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
        return parsed.astimezone(IST)
    except ValueError:
        return None


def extract_ltcp(feed_entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize one instrument feed block to LTP-centric dict."""
    if not isinstance(feed_entry, dict):
        return {}
    full = feed_entry.get("fullFeed") or feed_entry.get("full_feed") or {}
    lt = feed_entry.get("ltpc") or feed_entry.get("LTPC") or {}
    index = full.get("indexFF") or full.get("index_ff") or {}
    market = full.get("marketFF") or full.get("market_ff") or full.get("marketLevel") or {}
    quote = (
        index.get("ltpc")
        or index.get("marketLevel")
        or market.get("ltpc")
        or market.get("optionChain")
        or lt
    )
    if not quote and lt:
        quote = lt
    if isinstance(quote, dict) and "ltpc" in quote and isinstance(quote["ltpc"], dict):
        quote = quote["ltpc"]
    ltp = quote.get("ltp") or quote.get("lastPrice") or quote.get("last_price")
    if ltp is None:
        return {}
    out: dict[str, Any] = {
        "ltp": float(ltp),
        "ltq": quote.get("ltq") or quote.get("lastTradedQuantity"),
        "volume_traded": quote.get("vtt") or quote.get("volumeTraded") or quote.get("volume"),
        "oi": quote.get("oi") or quote.get("openInterest"),
        "tbq": quote.get("tbq") or quote.get("totalBuyQuantity"),
        "tsq": quote.get("tsq") or quote.get("totalSellQuantity"),
        "timestamp": parse_upstox_timestamp(
            quote.get("ltt") or quote.get("lastTradeTime") or quote.get("ts")
        ),
    }
    ohlc = quote.get("ohlc") or market.get("ohlc") or {}
    if isinstance(ohlc, dict):
        out.update(
            {
                "open": ohlc.get("open"),
                "high": ohlc.get("high"),
                "low": ohlc.get("low"),
                "close": ohlc.get("close"),
            }
        )
    depth = market.get("marketLevel") or market.get("depth") or quote.get("depth")
    if isinstance(depth, dict):
        out["depth"] = depth
    return out


@dataclass
class WsHealth:
    connects: int = 0
    disconnects: int = 0
    messages: int = 0
    ticks: int = 0
    last_error: str | None = None
    last_message_at: str | None = None
    last_disconnect_at: str | None = None
    connected: bool = False


@dataclass
class UpstoxMarketWebSocket:
    """Blocking WebSocket worker with auto-reconnect (for shadow scripts)."""

    instrument_keys: list[str]
    mode: str = "full"
    on_ticks: Callable[[dict[str, dict[str, Any]]], None] | None = None
    on_control: Callable[[dict[str, Any]], None] | None = None
    reconnect_base_sec: float = 2.0
    reconnect_max_sec: float = 60.0
    rest: UpstoxRestClient = field(default_factory=UpstoxRestClient)
    health: WsHealth = field(default_factory=WsHealth)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)

    def stop(self) -> None:
        self._stop.set()

    def _run_once(self) -> None:
        import asyncio
        import websockets

        async def _session() -> None:
            uri = self.rest.authorize_ws_v3()
            ssl_ctx = ssl.create_default_context()
            async with websockets.connect(
                uri,
                ssl=ssl_ctx,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=8 * 1024 * 1024,
            ) as ws:
                self.health.connected = True
                self.health.connects += 1
                sub = {
                    "guid": "",
                    "method": "sub",
                    "data": {"mode": self.mode, "instrumentKeys": self.instrument_keys},
                }
                await ws.send(json.dumps(sub))
                while not self._stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        await ws.ping()
                        continue
                    self.health.messages += 1
                    self.health.last_message_at = datetime.now(timezone.utc).isoformat()
                    decoded = decode_feed_message(raw)
                    if not decoded:
                        continue
                    feeds = decoded.get("feeds") or {}
                    if not feeds:
                        if self.on_control:
                            self.on_control(decoded)
                        continue
                    batch: dict[str, dict[str, Any]] = {}
                    for key, entry in feeds.items():
                        tick = extract_ltcp(entry if isinstance(entry, dict) else {})
                        if tick:
                            batch[str(key)] = tick
                    if batch:
                        self.health.ticks += len(batch)
                        if self.on_ticks:
                            self.on_ticks(batch)
                    elif self.on_control:
                        self.on_control(decoded)

        asyncio.run(_session())

    def run_forever(self) -> None:
        backoff = self.reconnect_base_sec
        while not self._stop.is_set():
            try:
                self._run_once()
            except Exception as exc:  # noqa: BLE001 — shadow reconnect loop
                self.health.connected = False
                self.health.disconnects += 1
                self.health.last_error = f"{type(exc).__name__}:{exc}"
                self.health.last_disconnect_at = datetime.now(timezone.utc).isoformat()
                logger.warning("upstox_ws_disconnect %s", self.health.last_error)
            if self._stop.is_set():
                break
            time.sleep(backoff)
            backoff = min(self.reconnect_max_sec, backoff * 1.7)


def write_json_atomic(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)
