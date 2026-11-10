"""Wire ingestor ticks → book engine → thesis engine (v2 candle-close gating)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from thesis.book_engine import BookDivergenceEngine
from thesis.candle_builder import ClosedCandle1m
from thesis.registry import TradeRegistry
from thesis.thesis_engine import ThesisEngine
from thesis.types import TickInput


EventCallback = Callable[[str, dict], None]


@dataclass
class WsMailbox:
    events: deque = field(default_factory=deque)


class ThesisPipeline:
    def __init__(
        self,
        *,
        registry: TradeRegistry,
        book_engine: BookDivergenceEngine | None = None,
        thesis_engine: ThesisEngine | None = None,
    ) -> None:
        self.registry = registry
        self.book_engine = book_engine or BookDivergenceEngine()
        self.thesis_engine = thesis_engine or ThesisEngine()
        self._ws_mailboxes: dict[str, list[WsMailbox]] = {}
        self._sync_listeners: list[EventCallback] = []

    def register_trade(self, trade_id: str, thesis) -> None:
        self.thesis_engine.register_trade(trade_id, thesis)

    def on_tick(self, symbol: str, tick: TickInput) -> None:
        book = self.book_engine.evaluate_tick(symbol, tick)
        for rec in self.registry.active_for_symbol(symbol):
            out = self.thesis_engine.on_tick(
                rec.trade_id,
                rec.thesis,
                tick,
                book,
                updated_conditions=rec.conditions,
            )
            rec.last_book = book
            if out.confirmed:
                for event_type in rec.note_output(out, tick.timestamp):
                    self._emit(rec.trade_id, event_type, out, tick.timestamp)
                rec.last_thesis = out

    def on_candle_closed(self, symbol: str, candle: ClosedCandle1m) -> None:
        from thesis.runtime import ThesisRuntime  # noqa: PLC0415 — avoid cycle at import

        rt = ThesisRuntime.get()
        tick = rt.store.latest_tick(symbol)
        if tick is None:
            return
        book = self.book_engine.on_candle_close(symbol, candle, tick)
        for rec in self.registry.active_for_symbol(symbol):
            out = self.thesis_engine.on_candle_close(
                rec.trade_id,
                rec.thesis,
                candle,
                tick,
                book,
                updated_conditions=rec.conditions,
            )
            rec.last_book = book
            if out.confirmed:
                ts = float(candle.minute_start)
                for event_type in rec.note_output(out, ts):
                    self._emit(rec.trade_id, event_type, out, ts, candle=candle)
                rec.last_thesis = out

    def _emit(
        self,
        trade_id: str,
        event_type: str,
        out,
        timestamp: float,
        *,
        candle: ClosedCandle1m | None = None,
    ) -> None:
        payload = {
            "type": event_type,
            "trade_id": trade_id,
            "state": out.state.value,
            "reasons": list(out.reasons),
            "decision_line": out.decision_line,
            "annotation": out.annotation,
            "intermediate_signal": (
                out.intermediate_signal.value if out.intermediate_signal else None
            ),
            "timestamp": timestamp,
            "candle_minute_start": (
                candle.minute_start if candle else out.candle_minute_start
            ),
        }
        for fn in self._sync_listeners:
            fn(trade_id, payload)
        for box in self._ws_mailboxes.get(trade_id, []):
            box.events.append(payload)

    def subscribe_sync(self, fn: EventCallback) -> None:
        self._sync_listeners.append(fn)

    def subscribe_ws(self, trade_id: str) -> WsMailbox:
        box = WsMailbox()
        self._ws_mailboxes.setdefault(trade_id, []).append(box)
        return box

    def unsubscribe_ws(self, trade_id: str, box: WsMailbox) -> None:
        lst = self._ws_mailboxes.get(trade_id, [])
        if box in lst:
            lst.remove(box)
