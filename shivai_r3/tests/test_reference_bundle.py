"""The vendored R3 kernel stays byte-identical and its own suite stays green."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[1] / "reference"
EXPECTED_SHA256 = {
    "shivai_core.py": "82e92b97e8a6573510745a8a15aaff2abad108e966ed563c7c0a4b6c1d61d4f4",
    "test_shivai_core.py": "c367cd56b83892e59f37cb6a8ca35ff74aeae1aee432554877d93b934a0a98b6",
    "README.md": "8c4e2bed48d1f6935e5ba3ea491b075b04aaa3701726a84b5fac27d626d43285",
}


class ReferenceBundleTests(unittest.TestCase):
    def test_kernel_bytes_match_the_r3_bundle(self):
        for name, digest in EXPECTED_SHA256.items():
            found = hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest()
            self.assertEqual(found, digest, name)

    def test_reference_suite_passes(self):
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", "test_shivai_core.py"],
            cwd=REFERENCE,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Ran 8 tests", completed.stderr)

    def test_module_printer_emits_three_snapshots(self):
        root = REFERENCE.parents[1]
        completed = subprocess.run(
            [sys.executable, "-m", "shivai_r3"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.count("NO_VALID_TRADE"), 3)
        self.assertEqual(completed.stdout.count("MARKET STRUCTURE"), 3)
        self.assertEqual(completed.stdout.count("PLAN / OUTCOME"), 3)
        self.assertNotIn("LIVE_VERIFIED", completed.stdout)
        self.assertNotIn("DATA_STALE", completed.stdout)
        self.assertNotIn("CLOSED/HISTORICAL", completed.stdout)
        self.assertNotIn("BUY", completed.stdout)
        self.assertNotIn("SELL", completed.stdout)


if __name__ == "__main__":
    unittest.main()
