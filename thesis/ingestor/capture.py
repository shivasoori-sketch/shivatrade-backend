"""Phase 0 capture mode: record full-mode broker payloads to JSONL for one session."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TextIO

if TYPE_CHECKING:
    from thesis.ingestor.feed import FeedIngestor

BrokerName = Literal["upstox", "zerodha", "kite"]


@dataclass
class CaptureSession:
    """Append-only JSONL writer for replay / candle validation."""

    path: Path
    broker: BrokerName
    session_id: str = field(default_factory=lambda: time.strftime("%Y%m%d"))
    _fh: TextIO | None = field(default=None, repr=False)
    line_count: int = 0

    def open(self) -> CaptureSession:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        return self

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> CaptureSession:
        return self.open()

    def __exit__(self, *exc: object) -> None:
        self.close()

    def record(
        self,
        symbol: str,
        raw: dict,
        *,
        timestamp: float | None = None,
        mode: str = "full",
    ) -> None:
        if self._fh is None:
            raise RuntimeError("CaptureSession not open; call open() first")
        ts = float(timestamp if timestamp is not None else time.time())
        row = {
            "symbol": symbol,
            "broker": self.broker,
            "session_id": self.session_id,
            "mode": mode,
            "ts": ts,
            "raw": raw,
        }
        self._fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        self._fh.flush()
        self.line_count += 1

    @staticmethod
    def load_records(path: Path) -> list[dict]:
        out: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out


def replay_capture(path: Path, ingestor: "FeedIngestor") -> int:
    """Replay a Phase 0 JSONL session through the ingestor (zero-gap validation)."""
    count = 0
    for row in CaptureSession.load_records(path):
        ts = row.get("ts")
        ingestor.on_raw_tick(
            str(row["symbol"]),
            dict(row["raw"]),
            timestamp=float(ts) if ts is not None else None,
        )
        count += 1
    return count


def attach_capture(ingestor: object, session: CaptureSession) -> None:
    """Wire capture onto FeedIngestor (sets capture_session attribute)."""
    setattr(ingestor, "capture_session", session)
