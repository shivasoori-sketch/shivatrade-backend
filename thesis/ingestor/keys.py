"""Redis key patterns from THESIS spec §5.1."""

WINDOW_CAP = 20


def tick_hash(symbol: str) -> str:
    return f"tick:{symbol}"


def win_ltp(symbol: str) -> str:
    return f"win:ltp:{symbol}"


def win_vtt(symbol: str) -> str:
    return f"win:vtt:{symbol}"


def win_oi(symbol: str) -> str:
    return f"win:oi:{symbol}"


def baseline_depth(symbol: str) -> str:
    return f"baseline:depth:{symbol}"


def baseline_vol(symbol: str) -> str:
    return f"baseline:vol:{symbol}"


def data_stale_key(symbol: str) -> str:
    return f"meta:data_stale:{symbol}"
