import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from tests.test_cli import CHILD, TEMP
from tests.test_model import ROOT, FROZEN


class DemoTests(unittest.TestCase):
    def test_demo_full_report_and_exclusive_reuse(self):
        TEMP.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TEMP) as temp:
            output = Path(temp) / "demo.json"
            command = CHILD + ["-m", "scripts.demo_reports", "--output", str(output)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 4)
            self.assertEqual(result.stdout, b"")
            case = next(c for c in FROZEN["cases"] if c["label"] == "late-test-rollback")
            saved = output.read_bytes()
            self.assertEqual(json.loads(saved), case["expected"])
            repeated = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
            self.assertEqual(repeated.returncode, 2)
            self.assertEqual(json.loads(repeated.stderr)["reason"], "I/O or output delivery failed")
            self.assertEqual(saved, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
