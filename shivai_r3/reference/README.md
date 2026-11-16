# SHIVAI R3 reference kernel

This is **not a production trading bot**, does not connect to any broker, and always sets `entry_eligible=False`.

Run from this directory using Python 3.12+:

```bash
python3 -m unittest -v test_shivai_core.py
```

Files:
- `shivai_core.py`: data classes, baseline acceptance transitions, option quote rejection, simplistic research ranking, irreversible virtual stop and atomic research snapshot.
- `test_shivai_core.py`: a minimal behavior smoke suite, *not* the required 20+ determinism fixtures.
- `../SHIVAI_R3_0_MASTER_ARCHITECTURE_AND_IMPLEMENTATION.md`: normative design and unclosed implementation gates.

Do not treat the fixed 0.25 ATR breakout baseline, momentum ranking coefficients, or demonstration stops and targets as empirically validated.

No secrets, credentials, WebSockets, live API calls, filesystem writers, HTTP servers or orders are implemented.
