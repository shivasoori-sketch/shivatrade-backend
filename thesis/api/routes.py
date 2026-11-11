"""THESIS FastAPI routes (§5.4)."""

from __future__ import annotations

import asyncio
import json
import os
import time

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from thesis.api.schemas import (
    ActiveTradeResponse,
    BookResponse,
    ConditionIn,
    CreateTradeRequest,
    CreateTradeResponse,
    DepthPanelOut,
    ExitRequest,
    ExitResponse,
    IngestHealthResponse,
    IngestTickRequest,
    IngestTickResponse,
    StateResponse,
    TradeSummaryResponse,
)
from thesis.runtime import get_runtime
from thesis.session_watch import SESSION_WATCH_MESSAGE, ensure_session_watch_trade
from thesis.types import Direction, ThesisCondition, TradeThesis

router = APIRouter(prefix="", tags=["thesis"])


def _ingest_allowed(request: Request) -> bool:
    host = (request.client.host if request.client else "").lower()
    if host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return True
    return os.environ.get("THESIS_INGEST_ALLOW_REMOTE", "") == "1"


def _depth_panel(rt, rec) -> DepthPanelOut:
    sym = rec.thesis.symbol
    stale = rt.store.is_data_stale(sym)
    tick = rt.store.latest_tick(sym)
    vol = (
        "Awaiting candle close for follow-through read"
        if not stale
        else "Feed gap — data marked stale"
    )
    oi = "From ingest ticks (OI on candle close)" if tick else "Awaiting ingest ticks"
    session = (
        f"Session watch · {sym}"
        if rec.watch_kind == "session_watch"
        else f"Locked thesis · {sym}"
    )
    return DepthPanelOut(
        structure="Thesis rules on candle close (not tick color)",
        volume=vol,
        oi=oi,
        session=session,
    )


def _trade_summary(rec) -> TradeSummaryResponse:
    t = rec.thesis
    mode = rec.watch_kind if rec.watch_kind else "user"
    return TradeSummaryResponse(
        trade_id=rec.trade_id,
        symbol=t.symbol,
        direction=t.direction.value,
        entry_price=t.entry_price,
        stop_loss=t.stop_loss,
        target=t.target,
        status=rec.status,
        book_score_baseline=rec.book_score_baseline,
        created_at=rec.created_at,
        mode=mode,
        session_message=SESSION_WATCH_MESSAGE if mode == "session_watch" else "",
    )


def _conditions_from_schema(items: list[ConditionIn]) -> list[ThesisCondition]:
    return [
        ThesisCondition(
            id=c.id, label=c.label, met=c.met, is_core=c.is_core
        )
        for c in items
    ]


@router.get("/ingest/health", response_model=IngestHealthResponse)
def ingest_health() -> IngestHealthResponse:
    return IngestHealthResponse()


@router.post("/ingest/tick", response_model=IngestTickResponse)
def ingest_tick(body: IngestTickRequest, request: Request) -> IngestTickResponse:
    if not _ingest_allowed(request):
        raise HTTPException(status_code=403, detail="ingest allowed from localhost only")
    rt = get_runtime()
    rt.ingestor.on_raw_tick(body.symbol, body.raw, timestamp=body.ts)
    return IngestTickResponse(data_stale=rt.store.is_data_stale(body.symbol))


@router.post("/trade", response_model=CreateTradeResponse)
def create_trade(body: CreateTradeRequest) -> CreateTradeResponse:
    rt = get_runtime()
    conditions = _conditions_from_schema(body.conditions)
    thesis = TradeThesis(
        symbol=body.symbol,
        direction=Direction(body.direction),
        entry_price=body.entry_price,
        stop_loss=body.stop_loss,
        target=body.target,
        book_score_baseline=body.book_score_baseline or 0,
        dwell_seconds=body.dwell_seconds,
        conditions=conditions,
    )
    baseline = body.book_score_baseline
    tick = rt.store.latest_tick(body.symbol)
    if baseline is None and tick is not None:
        book = rt.pipeline.book_engine.evaluate(body.symbol, tick)
        baseline = book.book_score
    if baseline is None:
        baseline = 50
    rec = rt.registry.create(thesis, conditions, book_score_baseline=baseline)
    rec.watch_kind = "user"
    rt.pipeline.register_trade(rec.trade_id, thesis)
    if tick is not None:
        rt.pipeline.on_tick(body.symbol, tick)
    return CreateTradeResponse(
        trade_id=rec.trade_id,
        book_score_baseline=baseline,
    )


@router.get("/trade/active", response_model=ActiveTradeResponse)
def get_active_trade() -> ActiveTradeResponse:
    rt = get_runtime()
    rec = ensure_session_watch_trade(rt)
    summary = _trade_summary(rec)
    return ActiveTradeResponse(**summary.model_dump())


@router.get("/trade/{trade_id}", response_model=TradeSummaryResponse)
def get_trade(trade_id: str) -> TradeSummaryResponse:
    if trade_id == "active":
        raise HTTPException(
            status_code=400,
            detail="use GET /trade/active for session watch",
        )
    rt = get_runtime()
    rec = rt.registry.get(trade_id)
    if not rec:
        raise HTTPException(status_code=404, detail="trade not found")
    return _trade_summary(rec)


@router.get("/trade/{trade_id}/state", response_model=StateResponse)
def get_trade_state(trade_id: str) -> StateResponse:
    rt = get_runtime()
    rec = rt.registry.get(trade_id)
    if not rec:
        raise HTTPException(status_code=404, detail="trade not found")
    depth = _depth_panel(rt, rec)
    mode = rec.watch_kind or "user"
    if not rec.last_thesis:
        return StateResponse(
            trade_id=trade_id,
            state="HOLDS",
            reasons=[],
            decision_line="HOLD",
            conditions=[
                ConditionIn(id=c.id, label=c.label, met=c.met, is_core=c.is_core)
                for c in rec.conditions
            ],
            data_stale=rt.store.is_data_stale(rec.thesis.symbol),
            mode=mode,
            depth=depth,
        )
    out = rec.last_thesis
    return StateResponse(
        trade_id=trade_id,
        state=out.state.value,
        reasons=list(out.reasons),
        decision_line=out.decision_line,
        conditions=[
            ConditionIn(id=c.id, label=c.label, met=c.met, is_core=c.is_core)
            for c in out.conditions
        ],
        data_stale=rt.store.is_data_stale(rec.thesis.symbol),
        annotation=out.annotation,
        intermediate_signal=(
            out.intermediate_signal.value if out.intermediate_signal else None
        ),
        mode=mode,
        depth=depth,
    )


@router.get("/trade/{trade_id}/book", response_model=BookResponse)
def get_trade_book(trade_id: str) -> BookResponse:
    rt = get_runtime()
    rec = rt.registry.get(trade_id)
    if not rec:
        raise HTTPException(status_code=404, detail="trade not found")
    if not rec.last_book:
        raise HTTPException(
            status_code=409,
            detail="Awaiting candle close — book score updates on 1m close.",
        )
    b = rec.last_book
    return BookResponse(
        trade_id=trade_id,
        book_score=b.book_score,
        divergence_flag=b.divergence_flag,
        sweep_risk=b.sweep_risk,
        sub_scores={
            "absorption": b.sub_scores.absorption,
            "liquidity_vacuum": b.sub_scores.liquidity_vacuum,
            "oi_confirmation": b.sub_scores.oi_confirmation,
            "volume_follow_through": b.sub_scores.volume_follow_through,
        },
    )


@router.post("/trade/{trade_id}/exit", response_model=ExitResponse)
def exit_trade(trade_id: str, body: ExitRequest) -> ExitResponse:
    rt = get_runtime()
    rec = rt.registry.get(trade_id)
    if not rec:
        raise HTTPException(status_code=404, detail="trade not found")
    state_at_exit = (
        rec.last_thesis.state.value if rec.last_thesis else "HOLDS"
    )
    rec.status = "exited"
    rec.exit_payload = {
        "held_to_plan": body.held_to_plan,
        "exit_reason": body.exit_reason,
        "outcome_r": body.outcome_r,
        "state_at_exit": state_at_exit,
        "book_score_at_exit": (
            rec.last_book.book_score if rec.last_book else None
        ),
    }
    return ExitResponse(
        trade_id=trade_id,
        status="exited",
        state_at_exit=state_at_exit,
    )


@router.get("/external_signals")
def get_external_signals() -> dict:
    """KD / legacy feeds — read-only, off by default (spec §7)."""
    return {
        "enabled": False,
        "source": "kaaldrishti_legacy",
        "note": "Does not write to THESIS conviction state.",
        "signals": [],
    }


@router.get("/journal")
def get_journal() -> dict:
    rt = get_runtime()
    return {
        "trades": rt.registry.journal_entries(),
        "discipline_metrics_stub": {
            "held_to_plan_pct": None,
            "note": "Postgres journal lands in a later phase",
        },
    }


@router.websocket("/trade/{trade_id}/stream")
async def trade_state_stream(websocket: WebSocket, trade_id: str) -> None:
    rt = get_runtime()
    rec = rt.registry.get(trade_id)
    if not rec:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    mailbox = rt.pipeline.subscribe_ws(trade_id)
    last_ping = time.monotonic()
    try:
        while True:
            if mailbox.events:
                payload = mailbox.events.popleft()
                await websocket.send_text(json.dumps(payload))
                continue
            if time.monotonic() - last_ping > 30.0:
                await websocket.send_text(json.dumps({"type": "ping"}))
                last_ping = time.monotonic()
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        rt.pipeline.unsubscribe_ws(trade_id, mailbox)
