"""Runtime feature flags (env-driven). Book line defaults off until Gate 2."""

import os

THESIS_BOOK_LINE_ENABLED: bool = os.environ.get(
    "THESIS_BOOK_LINE_ENABLED", ""
).lower() in ("1", "true", "yes")
