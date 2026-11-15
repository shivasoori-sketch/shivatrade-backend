# SHIVAI R3 closed-session package

Research-only view of the Friday 13 Nov 2026 session closes for NIFTY, BANKNIFTY, and SENSEX. The package is not imported by `main.py`. It does not open a socket, place an order, write a snapshot file, or expose a route.

The page is the section 1 layout: one 3-minute spot chart and the five section 1 rows. Close views use reference `source_quality` `STALE`. A session with no proven socket uses `DEGRADED`. `entry_eligible` stays false. The plan row is the reference value `NO_VALID_TRADE`. Empty cells are values the reference did not compute. The page is not served.

The exchange clock is `last_trade_time` (Friday). The Saturday API response clock is stored next to it and is not the price time. Stage A live windows are deferred. Setup B is out of scope. The vendored kernel under `reference/` is the R3 fixture kernel, not a production engine.

## Tests

From `shivai_r3/reference`:

```bash
python3 -m unittest -v test_shivai_core.py
```

From the repository root:

```bash
python3 -m unittest discover -s shivai_r3/tests -t . -v
```
