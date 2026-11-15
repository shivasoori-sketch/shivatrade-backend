"""Isolated SHIVAI R3 closed-session research package.

The server module in main.py does not import this package. There is no
network client, no order path, and no route.
"""

__all__ = ["build_closed_snapshots"]


def __getattr__(name: str):
    if name == "build_closed_snapshots":
        from shivai_r3.snapshot import build_closed_snapshots

        return build_closed_snapshots
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
