"""Resolve Kite instrument_token ↔ THESIS symbol strings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KiteInstrument:
    token: int
    thesis_symbol: str
    exchange: str
    tradingsymbol: str


def thesis_symbol(exchange: str, tradingsymbol: str) -> str:
    return f"{exchange}:{tradingsymbol}"


def _manifest_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    return list(raw.get("instruments") or [])


def resolve_from_manifest(
    manifest: Path,
    *,
    exchange: str,
    tradingsymbol: str,
) -> KiteInstrument | None:
    ex = exchange.upper()
    sym = tradingsymbol.upper()
    for row in _manifest_rows(manifest):
        if str(row.get("exchange", "")).upper() != ex:
            continue
        if str(row.get("tradingsymbol", "")).upper() != sym:
            continue
        tok = int(row["instrument_token"])
        ts = str(row.get("tradingsymbol"))
        ex2 = str(row.get("exchange"))
        return KiteInstrument(tok, thesis_symbol(ex2, ts), ex2, ts)
    return None


def resolve_nifty_month_fut(kite, *, prefix: str = "NIFTY") -> KiteInstrument | None:
    """Pick nearest NFO-FUT matching prefix (current month chain)."""
    instruments = kite.instruments("NFO")
    futs = [
        r
        for r in instruments
        if r.get("instrument_type") == "FUT"
        and str(r.get("name", "")).upper().startswith(prefix)
    ]
    if not futs:
        return None
    futs.sort(key=lambda r: str(r.get("expiry", "")))
    row = futs[0]
    tok = int(row["instrument_token"])
    ts = str(row["tradingsymbol"])
    ex = "NFO"
    return KiteInstrument(tok, thesis_symbol("NSE", ts), ex, ts)


def resolve_requested_symbols(
    kite,
    specs: list[str],
    *,
    manifest: Path | None = None,
) -> list[KiteInstrument]:
    """Parse THESIS_INGEST_SYMBOLS entries like NSE:SBIN or NFO:NIFTY26NOVFUT."""
    manifest = manifest or Path(
        os.environ.get(
            "THESIS_INSTRUMENT_MANIFEST",
            "/opt/shivtrade/shared/ws_market_data/instruments.json",
        )
    )
    out: list[KiteInstrument] = []
    seen: set[int] = set()
    for spec in specs:
        spec = spec.strip()
        if not spec or ":" not in spec:
            continue
        ex, sym = spec.split(":", 1)
        inst = resolve_from_manifest(manifest, exchange=ex, tradingsymbol=sym)
        if inst is None and ex.upper() == "NSE" and sym.upper().startswith("NIFTY") and "FUT" in sym.upper():
            inst = resolve_nifty_month_fut(kite, prefix="NIFTY")
        if inst is None and kite is not None:
            rows = kite.instruments(ex if ex != "NSE" else "NSE")
            match = [
                r
                for r in rows
                if str(r.get("tradingsymbol", "")).upper() == sym.upper()
            ]
            if match:
                row = match[0]
                tok = int(row["instrument_token"])
                ts = str(row["tradingsymbol"])
                ex2 = str(row.get("exchange", ex))
                inst = KiteInstrument(tok, thesis_symbol(ex2 if ex2 != "NFO" else "NSE", ts), ex2, ts)
        if inst is None:
            continue
        if inst.token in seen:
            continue
        seen.add(inst.token)
        out.append(inst)
    return out
