"""Wire ingestor ticks → book engine → thesis engine."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from thesis.book_engine import BookDivergenceEngine
from thesis.registry import TradeRegistry
from thesis.thesis_engine import ThesisEngine
from thesis.types import ThesisCondition, TickInput


StateChangeCallback = Callable[[str, dict], None]


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
        self._sync_listeners: list[StateChangeCallback] = []

    def register_trade(self, trade_id: str, thesis) -> None:
        self.thesis_engine.register_trade(trade_id, thesis)

    def on_tick(self, symbol: str, tick: TickInput) -> None:
        book = self.book_engine.evaluate(symbol, tick)
        for rec in self.registry.active_for_symbol(symbol):
            out = self.thesis_engine.step(
                rec.trade_id,
                rec.thesis,
                tick,
                book,
                updated_conditions=rec.conditions,
            )
            changed = rec.note_state_change(out, tick.timestamp)
            rec.last_book = book
            rec.last_thesis = out
            if changed:
                payload = {
                    "trade_id": rec.trade_id,
                    "state": out.state.value,
                    "reasons": list(out.reasons),
                    "decision_line": out.decision_line,
                    "timestamp": tick.timestamp,
                }
                for fn in self._sync_listeners:
                    fn(rec.trade_id, payload)
                for box in self._ws_mailboxes.get(rec.trade_id, []):
                    box.events.append(payload)

    def subscribe_sync(self, fn: StateChangeCallback) -> None:
        self._sync_listeners.append(fn)

    def subscribe_ws(self, trade_id: str) -> WsMailbox:
        box = WsMailbox()
        self._ws_mailboxes.setdefault(trade_id, []).append(box)
        return box

    def unsubscribe_ws(self, trade_id: str, box: WsMailbox) -> None:
        lst = self._ws_mailboxes.get(trade_id, [])
        if box in lst:
            lst.remove(box)
