"""Load verified Zerodha session from ShivaTrade brokers.json (no secret logging)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KiteBind:
    ok: bool
    reason: str
    api_key: str
    access_token: str
    user_id: str

    @property
    def redacted(self) -> str:
        return f"user_id={self.user_id or '?'} reason={self.reason}"


def _pick_account(accounts: list[dict], account_id: str) -> dict | None:
    for acc in accounts:
        if str(acc.get("account_id")) == account_id:
            return acc
    return None


def load_kite_bind(
    *,
    brokers_path: Path | None = None,
    account_id: str | None = None,
) -> KiteBind:
    path = brokers_path or Path(
        os.environ.get(
            "SHIVTRADE_BROKERS_JSON",
            "/opt/shivtrade/shared/config/brokers.json",
        )
    )
    account_id = account_id or os.environ.get("THESIS_KITE_ACCOUNT_ID", "kite_main")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return KiteBind(False, f"BROKERS_READ:{exc.__class__.__name__}", "", "", "")
    except json.JSONDecodeError:
        return KiteBind(False, "BROKERS_JSON_INVALID", "", "", "")

    account = _pick_account(list(raw.get("accounts") or []), account_id)
    if not account:
        return KiteBind(False, "ACCOUNT_MISSING", "", "", "")
    creds = account.get("credentials") or {}
    session = account.get("session") or {}
    api_key = str(creds.get("api_key") or "").strip()
    access_token = str(session.get("access_token") or "").strip()
    user_id = str(session.get("user_id") or "").strip()
    if not session.get("logged_in"):
        return KiteBind(False, "NOT_LOGGED_IN", api_key, "", user_id)
    auth = session.get("auth_status")
    if auth not in (None, "", "VERIFIED"):
        return KiteBind(False, f"AUTH_{auth}", api_key, "", user_id)
    if not api_key or not access_token:
        return KiteBind(False, "MISSING_TOKEN", api_key, "", user_id)
    return KiteBind(True, "OK", api_key, access_token, user_id)
