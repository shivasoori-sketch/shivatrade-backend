"""In-memory trade registry + journal stub (Phase 1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from thesis.types import BookOutput, ThesisCondition, ThesisOutput, ThesisState, TradeThesis


@dataclass
class StateTransition:
    timestamp: float
    from_state: ThesisState | None
    to_state: ThesisState
    reasons: tuple[str, ...]
    decision_line: str


@dataclass
class TradeRecord:
    trade_id: str
    thesis: TradeThesis
    conditions: list[ThesisCondition]
    status: str = "active"
    book_score_baseline: int = 0
    last_book: BookOutput | None = None
    last_thesis: ThesisOutput | None = None
    transitions: list[StateTransition] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    exit_payload: dict | None = None

    def note_state_change(self, output: ThesisOutput, ts: float) -> bool:
        prev = self.last_thesis.state if self.last_thesis else None
        if prev == output.state:
            return False
        self.transitions.append(
            StateTransition(
                timestamp=ts,
                from_state=prev,
                to_state=output.state,
                reasons=output.reasons,
                decision_line=output.decision_line,
            )
        )
        return True


class TradeRegistry:
    def __init__(self) -> None:
        self._trades: dict[str, TradeRecord] = {}
        self._by_symbol: dict[str, list[str]] = {}

    def create(
        self,
        thesis: TradeThesis,
        conditions: list[ThesisCondition],
        *,
        book_score_baseline: int | None = None,
    ) -> TradeRecord:
        trade_id = str(uuid.uuid4())
        baseline = book_score_baseline if book_score_baseline is not None else thesis.book_score_baseline
        thesis.book_score_baseline = baseline
        rec = TradeRecord(
            trade_id=trade_id,
            thesis=thesis,
            conditions=list(conditions),
            book_score_baseline=baseline,
        )
        self._trades[trade_id] = rec
        self._by_symbol.setdefault(thesis.symbol, []).append(trade_id)
        return rec

    def get(self, trade_id: str) -> TradeRecord | None:
        return self._trades.get(trade_id)

    def active_for_symbol(self, symbol: str) -> list[TradeRecord]:
        ids = self._by_symbol.get(symbol, [])
        return [
            self._trades[i]
            for i in ids
            if self._trades[i].status == "active"
        ]

    def journal_entries(self) -> list[dict]:
        rows = []
        for rec in self._trades.values():
            rows.append(
                {
                    "trade_id": rec.trade_id,
                    "symbol": rec.thesis.symbol,
                    "status": rec.status,
                    "state": (
                        rec.last_thesis.state.value if rec.last_thesis else None
                    ),
                    "created_at": rec.created_at,
                    "exit": rec.exit_payload,
                    "transition_count": len(rec.transitions),
                }
            )
        return rows
