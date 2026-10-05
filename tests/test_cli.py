import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from patch_lab.__main__ import main, write_checked
from patch_lab.contract import LabError, read
from tests.test_model import ROOT, FROZEN, env


def wire(value):
    return json.dumps(value,ensure_ascii=False,separators=(",", ":")).encode("utf-8")

CHILD = [sys.executable] + (["-O"] if sys.flags.optimize else [])
RUN = CHILD + ["-m", "patch_lab"]
TEMP = ROOT / ".private" / "tests"


class DirtySink:
    def __init__(self, failure):
        self.failure, self.content = failure, ""

    def write(self, text):
        self.content += text
        if self.failure == "write":
            raise OSError("private sink detail")
        return len(text) - 1 if self.failure == "short" else len(text)

    def flush(self):
        if self.failure == "flush":
            raise OSError("private flush detail")


class CLITests(unittest.TestCase):
    def setUp(self):
        TEMP.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=TEMP)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.input = self.folder / "input.json"
        self.input.write_bytes(wire(env({"a": None}, [])))

    def invoke(self, *args):
        return subprocess.run(RUN + [str(a) for a in args], cwd=ROOT, capture_output=True, timeout=20)

    def test_actual_reports_and_fixed_errors(self):
        for case in FROZEN["cases"]:
            with self.subTest(name=case["label"]):
                self.input.write_bytes(wire(case["input"]))
                result = self.invoke(self.input)
                self.assertEqual(result.returncode, case["exit"])
                self.assertEqual(json.loads(result.stdout), case["expected"])
                self.assertEqual(result.stdout,(json.dumps(case["expected"],ensure_ascii=True,sort_keys=True,separators=(",", ":"))+"\n").encode("ascii"))
                self.assertEqual(result.stderr, b"")
        for case in FROZEN["errors"]:
            with self.subTest(name=case["label"]):
                self.input.write_bytes(case["raw"].encode("utf-8"))
                result = self.invoke(self.input)
                self.assertEqual(result.returncode, case["exit"])
                self.assertEqual(result.stdout, b"")
                self.assertEqual(json.loads(result.stderr), case["expected"])

    def test_fresh_existing_alias_and_hardlink_output(self):
        original = self.input.read_bytes()
        output = self.folder / "fresh.json"
        good = self.invoke(self.input, "--output", output)
        self.assertEqual(good.returncode, 0)
        self.assertEqual(good.stdout, b"")
        self.assertFalse(json.loads(output.read_bytes())["changed"])
        saved = output.read_bytes()
        for target in (output, self.input):
            result = self.invoke(self.input, "--output", target)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
        link = self.folder / "alias.json"
        os.link(self.input, link)
        result = self.invoke(self.input, "--output", link)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.input.read_bytes(), original)
        self.assertEqual(link.read_bytes(), original)
        self.assertEqual(output.read_bytes(), saved)

    def test_empty_paths_missing_nul_and_arguments(self):
        for args in ((self.input, "--output", ""), ("",), (self.folder,),
                     (self.folder / "missing",), (), ("--unknown",)):
            result = self.invoke(*args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(json.loads(result.stderr)["status"], "error")
        for args in (("bad\0path",), (str(self.input), "--output", "bad\0path")):
            error = io.StringIO()
            with patch("sys.stderr", error):
                self.assertEqual(main(list(args)), 2)
            self.assertEqual(json.loads(error.getvalue())["reason"], "I/O or output delivery failed")
        help_result = self.invoke("--help")
        self.assertEqual(help_result.returncode, 0)
        self.assertIn(b"JSON Patch", help_result.stdout)

    def test_dirty_short_flush_and_both_failed_sinks(self):
        for failure in ("write", "short", "flush"):
            for args in ([str(self.input)], ["--help"]):
                output, error = DirtySink(failure), io.StringIO()
                with patch("sys.stdout", output), patch("sys.stderr", error):
                    self.assertEqual(main(args), 2)
                self.assertTrue(output.content)
                self.assertEqual(json.loads(error.getvalue())["reason"], "I/O or output delivery failed")
            for args in ([str(self.input)], ["--help"], [str(self.folder / "missing")]):
                output, error = DirtySink(failure), DirtySink(failure)
                with patch("sys.stdout", output), patch("sys.stderr", error):
                    self.assertEqual(main(args), 2)
                    self.assertIsInstance(sys.stderr, io.StringIO)
                self.assertTrue(error.content)
                self.assertNotIn("private", error.content)

    def test_output_context_close_failure(self):
        @contextlib.contextmanager
        def broken_close(*_args, **_kwargs):
            yield io.StringIO()
            raise OSError("private close detail")
        original = self.input.read_bytes()
        output, error = io.StringIO(), io.StringIO()
        with patch("pathlib.Path.open", broken_close), patch("sys.stdout", output), patch("sys.stderr", error):
            self.assertEqual(main([str(self.input), "--output", str(self.folder / "new")]), 2)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(json.loads(error.getvalue())["reason"], "I/O or output delivery failed")
        self.assertEqual(self.input.read_bytes(), original)

    def test_write_count_requires_exact_integer(self):
        class WrongCount:
            def __init__(self, result):
                self.result = result

            def write(self, _text):
                return self.result

            def flush(self):
                pass

        for count in (None, True, False, 3.0):
            with self.subTest(count=count):
                content = "a" if count is True else "abc"
                self.assertRaises(OSError, write_checked, WrongCount(count), content)

    def test_output_file_dirty_write_and_flush(self):
        for failure in ("write", "short", "flush"):
            sink = DirtySink(failure)

            @contextlib.contextmanager
            def broken_file(*_args, **_kwargs):
                yield sink

            output, error = io.StringIO(), io.StringIO()
            with patch("pathlib.Path.open", broken_file), patch("sys.stdout", output), patch("sys.stderr", error):
                self.assertEqual(main([str(self.input), "--output", str(self.folder / "new")]), 2)
            self.assertTrue(sink.content)
            self.assertEqual(output.getvalue(), "")
            self.assertEqual(json.loads(error.getvalue())["reason"], "I/O or output delivery failed")

    def test_actual_closed_pipes_normal_or_optimized_child(self):
        # A stdin barrier closes reader endpoints before the child can deliver.
        script = "import sys,runpy; sys.stdin.buffer.read(1); runpy.run_module('patch_lab',run_name='__main__')"
        for args, close_stdout, close_stderr in (([str(self.input)], True, False),
                                                ([str(self.input)], True, True),
                                                (["--help"], True, False),
                                                (["--help"], True, True),
                                                ([str(self.folder / "missing")], False, True)):
            child = subprocess.Popen(CHILD + ["-c", script] + args, cwd=ROOT,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                if close_stdout:
                    child.stdout.close()
                if close_stderr:
                    child.stderr.close()
                child.stdin.write(b"x")
                child.stdin.flush()
                child.stdin.close()
                self.assertEqual(child.wait(timeout=20), 2)
                if not close_stdout:
                    self.assertEqual(child.stdout.read(), b"")
                if not close_stderr:
                    self.assertEqual(json.loads(child.stderr.read())["reason"], "I/O or output delivery failed")
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=20)
                for sink in (child.stdin, child.stdout, child.stderr):
                    sink.close()

    def test_invalid_and_overflow_emit_no_report_or_file(self):
        for source in (env(float("nan")),
                       FROZEN["overflow_uncapped"]["input"]):
            self.input.write_bytes(wire(source))
            output = self.folder / "absent.json"
            result = self.invoke(self.input, "--output", output)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertFalse(output.exists())
            self.assertIn(json.loads(result.stderr)["reason"], ("invalid input", "resource limit"))

    def test_bounded_regular_read_and_observed_metadata(self):
        self.assertEqual(read(self.input), self.input.read_bytes())
        self.assertRaises(LabError, read, self.folder)
        self.input.write_bytes(b" " * 65537)
        self.assertRaises(LabError, read, self.input)
        self.input.write_bytes(b"{}")
        original_stat = self.input.stat()
        changed = list(original_stat)
        changed[6] += 1
        with patch("patch_lab.contract.os.fstat", return_value=os.stat_result(changed)):
            self.assertRaises(OSError, read, self.input)
        with patch("patch_lab.contract.os.fstat", side_effect=[original_stat, os.stat_result(changed)]):
            self.assertRaises(OSError, read, self.input)


if __name__ == "__main__":
    unittest.main()
