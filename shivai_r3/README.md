# SHIVAI R3 closed-session package

Research-only snapshot of the Friday 13 Nov 2026 session closes for NIFTY 50, BANKNIFTY, and SENSEX. The package is not imported by `main.py`. It does not open a socket, place an order, write a snapshot file, or expose a route.

Every assessment is `CLOSED/HISTORICAL` with feed quality `DATA_STALE`. `entry_eligible` stays false. `ENTRY_POLICY_DISABLED` stays on. The plan row is `NO VALID TRADE`, highlighted reason `MARKET_CLOSED`.

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
