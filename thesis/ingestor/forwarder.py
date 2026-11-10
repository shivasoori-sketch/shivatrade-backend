"""HTTP forwarder: ingest process → THESIS API runtime (localhost)."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ThesisIngestForwarder:
    base_url: str
    timeout: float = 2.0
    batch: bool = False
    _client: httpx.Client | None = field(default=None, repr=False)
    _failures: int = 0
    _sent: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def _client_get(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def forward_tick(
        self,
        symbol: str,
        raw: dict[str, Any],
        *,
        timestamp: float | None = None,
    ) -> bool:
        body = {"symbol": symbol, "raw": raw, "ts": timestamp}
        url = f"{self.base_url}/ingest/tick"
        try:
            resp = self._client_get().post(url, json=body)
            resp.raise_for_status()
            with self._lock:
                self._sent += 1
                self._failures = 0
            return True
        except httpx.HTTPError as exc:
            with self._lock:
                self._failures += 1
            if self._failures <= 3 or self._failures % 50 == 0:
                logger.warning("ingest forward failed (%s): %s", self._failures, exc)
            return False

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    @property
    def sent(self) -> int:
        with self._lock:
            return self._sent

    @property
    def failures(self) -> int:
        with self._lock:
            return self._failures


def forwarder_from_env() -> ThesisIngestForwarder:
    base = os.environ.get("THESIS_API_URL", "http://127.0.0.1:5098")
    return ThesisIngestForwarder(base_url=base)


def wait_for_api(base_url: str, *, attempts: int = 30, delay: float = 1.0) -> bool:
    url = base_url.rstrip("/") + "/ingest/health"
    for _ in range(attempts):
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(delay)
    return False
