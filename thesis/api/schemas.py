"""FastAPI request/response models for THESIS §5.4."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConditionIn(BaseModel):
    id: str
    label: str
    met: bool = True
    is_core: bool = False


class CreateTradeRequest(BaseModel):
    symbol: str
    direction: str = Field(pattern="^(long|short)$")
    entry_price: float
    stop_loss: float
    target: float
    book_score_baseline: int | None = None
    dwell_seconds: float = 300.0
    conditions: list[ConditionIn] = Field(min_length=1, max_length=5)


class CreateTradeResponse(BaseModel):
    trade_id: str
    book_score_baseline: int
    status: str = "locked"


class TradeSummaryResponse(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    target: float
    status: str
    book_score_baseline: int
    created_at: str


class StateResponse(BaseModel):
    trade_id: str
    state: str
    reasons: list[str]
    decision_line: str
    conditions: list[ConditionIn]
    data_stale: bool = False


class BookResponse(BaseModel):
    trade_id: str
    book_score: int
    divergence_flag: bool
    sweep_risk: bool
    sub_scores: dict[str, int]


class ExitRequest(BaseModel):
    held_to_plan: bool = False
    exit_reason: str = "manual"
    outcome_r: float | None = None


class ExitResponse(BaseModel):
    trade_id: str
    status: str
    state_at_exit: str | None
