"""Isolated SHIVAI R3 view. main.py does not import this package."""

__all__ = ["close_views", "render_closes"]


def __getattr__(name: str):
    if name == "close_views":
        from shivai_r3.snapshot import close_views

        return close_views
    if name == "render_closes":
        from shivai_r3.page import render_closes

        return render_closes
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
