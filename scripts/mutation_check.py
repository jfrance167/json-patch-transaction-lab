"""Eight fixed assertion mutants in fresh isolated copies; source remains untouched.

Usage: python -m scripts.mutation_check FRESH_DIRECTORY
Input: trusted local runtime/tests/frozen fixtures. Output: copies, raw logs and
summary.json. No downloads, deletion, generated commands, or arbitrary mutants.
Expect each targeted unittest to fail by assertion, not syntax/import exceptions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = [('rollback-weakened', 'model.py', 'result = _clone(envelope["target"]) if failure is not None else _clone(working)', 'result = _clone(working)', 'test_rollback'), ('pre-removal-index', 'model.py', 'value = _remove(value, source)\n    return _add(value, path, moved)', 'if source[:-1] == path[:-1] and type(_lookup(value, source[:-1])) is list and path[-1].isdigit() and int(path[-1]) > int(source[-1]):\n        path = path[:-1] + [str(int(path[-1]) - 1)]\n    value = _remove(value, source)\n    return _add(value, path, moved)', 'test_post_removal_destination'), ('python-equality', 'model.py', 'if type(left) is not type(right):', 'if False:', 'test_typed_equality'), ('copy-alias', 'model.py', 'def _copy_value(value):\n    # Snapshot before insertion, especially when the source is the entire root.\n    return _clone(value)', 'def _copy_value(value):\n    return value', 'test_copy_detaches_working_subtree'), ('string-prefix-ancestry', 'model.py', 'if len(source) < len(path) and path[:len(source)] == source:', 'if "/".join(path).startswith("/".join(source)) and source != path:', 'test_decoded_ancestry'), ('missing-parent-created', 'model.py', 'return _lookup(value, path[:-1]), path[-1]', 'current = value\n    for token in path[:-1]:\n        if type(current) is dict:\n            current = current.setdefault(token, {})\n        else:\n            current = _lookup(current, [token])\n    return current, path[-1]', 'test_missing_parent'), ('node-cap', 'contract.py', "'result_nodes': 1024", "'result_nodes': 2048", 'test_node_growth'), ('output-cap', 'contract.py', "'output_bytes': 131072", "'output_bytes': 262144", 'test_output_cap_only')]

def hashes():
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("patch_lab", "tests", "fixtures") for p in sorted((ROOT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    resolved = args.output.resolve()
    if any(resolved.is_relative_to(ROOT / folder) for folder in ("patch_lab", "tests", "fixtures")):
        raise ValueError("mutation output must be outside copied source directories")
    args.output.mkdir(parents=True, exist_ok=False)
    before = hashes()
    results = []
    for name, file, original, replacement, test in MUTANTS:
        copy = args.output / name
        copy.mkdir()
        for folder in ("patch_lab", "tests", "fixtures"):
            shutil.copytree(ROOT / folder, copy / folder, ignore=shutil.ignore_patterns("__pycache__"))
        target = copy / "patch_lab" / file
        text = target.read_text(encoding="utf-8")
        if text.count(original) != 1:
            raise RuntimeError("mutation anchor must occur exactly once")
        target.write_text(text.replace(original, replacement), encoding="utf-8", newline="\n")
        command = [sys.executable, "-m", "unittest", "-v", "tests.test_model.ModelTests." + test]
        result = subprocess.run(command, cwd=copy, capture_output=True, timeout=30)
        log = result.stdout + result.stderr
        (copy / "result.log").write_bytes(log)
        detected = result.returncode == 1 and b"AssertionError" in log and b"FAILED (failures=1)" in log and b"ERROR:" not in log
        results.append({"name": name, "target_test": test, "exit": result.returncode,
                        "assertion_detected": detected, "log_sha256": hashlib.sha256(log).hexdigest()})
    unchanged = before == hashes()
    summary = {"mutants": results, "originals_unchanged": unchanged, "original_hashes": before}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    print(json.dumps({"detected": sum(r["assertion_detected"] for r in results), "total": len(results), "unchanged": unchanged}))
    return 0 if unchanged and all(r["assertion_detected"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
