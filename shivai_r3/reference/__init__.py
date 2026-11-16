"""Vendored R3 reference kernel.

Run `python3 -m unittest -v test_shivai_core.py` from this directory.
The kernel files are byte-for-byte copies. This marker is local to the package.
"""
import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
