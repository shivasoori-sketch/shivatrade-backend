"""KiteTicker full-mode → FeedIngestor + JSONL capture + HTTP forward to THESIS API."""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from kiteconnect import KiteConnect

from thesis.ingestor.adapters.zerodha import adapt_zerodha_tick
from thesis.ingestor.capture import CaptureSession
from thesis.ingestor.feed import FeedIngestor
from thesis.ingestor.forwarder import ThesisIngestForwarder, forwarder_from_env, wait_for_api
from thesis.ingestor.kite_bind import load_kite_bind
from thesis.ingestor.kite_symbols import KiteInstrument, resolve_requested_symbols
from thesis.ingestor.metrics import LiveIngestMetrics
from thesis.ingestor.redis_store import InMemoryRedisStore, ThesisRedisStore

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _default_session_path() -> Path:
    root = Path(
        os.environ.get(
            "THESIS_FEED_ROOT",
            "/opt/shivtrade/research/thesis-feed/sessions",
        )
    )
    day = datetime.now(IST).strftime("%Y-%m-%d")
    return root / f"{day}-zerodha-full.jsonl"


def _parse_symbols_env() -> list[str]:
    raw = os.environ.get(
        "THESIS_INGEST_SYMBOLS",
        "NSE:NIFTY26NOVFUT,NSE:SBIN,NSE:NIFTY 50",
    )
    return [s.strip() for s in raw.split(",") if s.strip()]


class ThesisKiteLiveIngest:
    def __init__(
        self,
        *,
        capture_path: Path,
        forwarder: ThesisIngestForwarder | None,
        instruments: list[KiteInstrument],
        bind_reason: str,
    ) -> None:
        self.capture_path = capture_path
        self.forwarder = forwarder
        self.instruments = instruments
        self.token_to_symbol = {i.token: i.thesis_symbol for i in instruments}
        self._metrics = LiveIngestMetrics(
            gap_threshold_seconds=float(os.environ.get("THESIS_GAP_THRESHOLD", "5"))
        )
        self._stop = threading.Event()
        self._ticker = None
        self._bind_reason = bind_reason
        store = ThesisRedisStore(InMemoryRedisStore())
        self._session = CaptureSession(capture_path, broker="zerodha").open()
        self._ingestor = FeedIngestor(
            store=store,
            build_candles=True,
            capture_session=self._session,
        )

    def _on_tick_batch(self, _ws: Any, ticks: list[dict]) -> None:
        for raw in ticks:
            tok = int(raw.get("instrument_token") or 0)
            symbol = self.token_to_symbol.get(tok)
            if not symbol:
                continue
            adapted = adapt_zerodha_tick(raw, symbol=symbol)
            ts = adapted.get("timestamp")
            epoch: float | None = None
            if isinstance(ts, datetime):
                epoch = ts.timestamp()
            elif isinstance(ts, (int, float)):
                epoch = float(ts)
            elif isinstance(ts, str):
                from thesis.ingestor.normalize import _parse_timestamp

                epoch = _parse_timestamp(ts)
            tick_input = self._ingestor.on_raw_tick(symbol, adapted, timestamp=epoch)
            if epoch is not None:
                self._metrics.note_tick(symbol, epoch)
            elif tick_input.timestamp > 0:
                self._metrics.note_tick(symbol, tick_input.timestamp)
            if self.forwarder:
                self.forwarder.forward_tick(
                    symbol, adapted, timestamp=epoch or tick_input.timestamp
                )

    def _on_connect(self, _ws: Any, _response: Any) -> None:
        tokens = list(self.token_to_symbol.keys())
        logger.info(
            "KiteTicker connected; subscribing %s tokens (%s)",
            len(tokens),
            self._bind_reason,
        )
        assert self._ticker is not None
        self._ticker.subscribe(tokens)
        self._ticker.set_mode(self._ticker.MODE_FULL, tokens)
        self._ingestor.mark_connected()

    def _on_close(self, _ws: Any, code: int, reason: str) -> None:
        logger.warning("KiteTicker closed code=%s reason=%s", code, reason)
        self._ingestor.mark_disconnected()

    def _on_error(self, _ws: Any, code: int, reason: str) -> None:
        logger.error("KiteTicker error code=%s reason=%s", code, reason)
        self._ingestor.mark_disconnected()

    def _metrics_loop(self) -> None:
        interval = float(os.environ.get("THESIS_METRICS_INTERVAL_SEC", "60"))
        while not self._stop.wait(interval):
            logger.info("%s", self._metrics.snapshot_line())

    def run(self, *, api_key: str, access_token: str) -> int:
        from kiteconnect import KiteTicker  # lazy — Twisted

        self._ticker = KiteTicker(api_key, access_token)
        self._ticker.on_ticks = self._on_tick_batch
        self._ticker.on_connect = self._on_connect
        self._ticker.on_close = self._on_close
        self._ticker.on_error = self._on_error
        self._ticker.connect(threaded=True)

        metrics_th = threading.Thread(target=self._metrics_loop, daemon=True)
        metrics_th.start()

        def _shutdown(*_args: object) -> None:
            logger.info("shutdown requested")
            self._stop.set()
            try:
                self._ticker.close()
            except Exception:
                pass
            self._session.close()
            if self.forwarder:
                self.forwarder.close()
            logger.info("%s", self._metrics.snapshot_line())
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        logger.info(
            "THESIS kite ingest running capture=%s symbols=%s",
            self.capture_path,
            sorted(set(self.token_to_symbol.values())),
        )
        while not self._stop.is_set():
            time.sleep(1.0)
        return 0


def build_live_ingest(
    *,
    capture_path: Path | None = None,
    forward: bool = True,
) -> ThesisKiteLiveIngest:
    bind = load_kite_bind()
    if not bind.ok:
        raise RuntimeError(f"Kite bind failed: {bind.reason}")
    kite = KiteConnect(api_key=bind.api_key)
    kite.set_access_token(bind.access_token)
    instruments = resolve_requested_symbols(kite, _parse_symbols_env())
    if not instruments:
        raise RuntimeError("No instruments resolved for THESIS ingest")
    path = capture_path or _default_session_path()
    fwd = forwarder_from_env() if forward else None
    api_url = fwd.base_url if fwd else os.environ.get("THESIS_API_URL", "http://127.0.0.1:5098")
    if forward and not wait_for_api(api_url):
        raise RuntimeError("THESIS API ingest/health not reachable")
    return ThesisKiteLiveIngest(
        capture_path=path,
        forwarder=fwd,
        instruments=instruments,
        bind_reason=bind.redacted,
    )


def run_live_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    bind = load_kite_bind()
    if not bind.ok:
        logger.error("Cannot start live ingest: %s", bind.reason)
        return 2
    ingest = build_live_ingest()
    return ingest.run(api_key=bind.api_key, access_token=bind.access_token)
