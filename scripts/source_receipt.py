"""Hash the completed local lab and assert saved verification records.

Usage: python -m scripts.source_receipt FRESH_JSON_PATH
Inputs: this lab's runtime/tests/fixtures/docs and accepted private logs.
Output: an exclusive SHA256/byte-length receipt, never source or secret values.
Assumptions: trusted local evidence, not authentication or an independent audit.
Verification: handoff rehashes every entry independently; fixed original fixture,
suite totals, scanner result and mutant assertions are checked before writing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_HASH = "7803075b3316b3311386d674bd1a377eb749669857bb1e13d516db7090fc7cd0"


def digest(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    verification = ROOT / ".private/verification"
    for name in ("final-normal.log", "final-optimized.log"):
        text = (verification / name).read_text(encoding="utf-8")
        if "Ran 34 tests" not in text or not text.rstrip().endswith("OK") or "skipped=" in text:
            raise RuntimeError("accepted suite record mismatch")
    scanner = json.loads((verification / "bandit-final-after-review.json").read_text())
    if scanner["results"] or scanner["errors"] or scanner["metrics"]["_totals"]["skipped_tests"] != 4:
        raise RuntimeError("scanner record mismatch")
    mutants = json.loads((verification / "mutations-final-after-review/summary.json").read_text())
    if len(mutants["mutants"]) != 8 or not mutants["originals_unchanged"]:
        raise RuntimeError("mutation record mismatch")
    if not all(row["assertion_detected"] and row["exit"] == 1 for row in mutants["mutants"]):
        raise RuntimeError("mutation assertion mismatch")
    for name, expected in mutants["original_hashes"].items():
        if digest(ROOT / name)["sha256"] != expected:
            raise RuntimeError("accepted mutation source changed")
    for row in mutants["mutants"]:
        log_path = verification / "mutations-final-after-review" / row["name"] / "result.log"
        log = log_path.read_bytes()
        if digest(log_path)["sha256"] != row["log_sha256"] or b"FAILED (failures=1)" not in log or b"AssertionError" not in log:
            raise RuntimeError("mutation raw log mismatch")
    if digest(ROOT / "fixtures/oracles.json")["sha256"] != FIXTURE_HASH:
        raise RuntimeError("original oracle changed")
    paths = list(ROOT.glob("*.md")) + [ROOT / "LICENSE", ROOT / ".gitignore", ROOT / "tasks/todo.md"]
    for folder in ("patch_lab", "tests", "scripts", "fixtures", "samples"):
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    source = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in sorted(set(paths))}
    # Targeted signatures only. Report locations/counts, never matching values.
    signatures = [rb"AKIA[0-9A-Z]{16}", rb"gh[pousr]_[A-Za-z0-9]{36,}",
                  rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"]
    found = [name for name in source if any(re.search(pattern, (ROOT / name).read_bytes()) for pattern in signatures)]
    if found:
        raise RuntimeError("targeted secret-signature match in task source")
    evidence_paths = [verification / name for name in
                      ("final-normal.log", "final-optimized.log", "bandit-final-after-review.json",
                       "bandit-final-after-review.log", "compile.log", "amplification.json",
                       "review-stdout-before-normal.log", "review-stdout-before-optimized.log", "review-stdout-after.log", "stage2.log", "stage2-fixed.log")]
    evidence_paths.extend((verification / "mutations-final-after-review").glob("*/result.log"))
    evidence_paths += [verification / "mutations-final-after-review/summary.json",
                       ROOT / ".private/research/freeze-v1.json",
                       ROOT / ".private/research/capture-provenance.json", ROOT / ".private/research/resource-construction.json", ROOT / ".private/research/freeze_oracles.py"]
    evidence = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in sorted(evidence_paths)}
    # Prior candidates are read-only retained evidence, not this product's code.
    prior_root = ROOT.parent / "json-merge-patch-lab" / ".private/research"
    prior_records = json.loads((prior_root / "capture-hashes.json").read_text())
    retained = {}
    for row in prior_records:
        if "/operation-list/" in row["path"]:
            actual = digest(prior_root / row["path"])
            if actual != {key: row[key] for key in ("bytes", "sha256")}:
                raise RuntimeError("retained candidate changed")
            retained["../json-merge-patch-lab/.private/research/" + row["path"]] = actual
    for path in (ROOT / ".private/research/schema-candidate").rglob("*"):
        if path.is_file():
            evidence[str(path.relative_to(ROOT)).replace("\\", "/")] = digest(path)
    frozen = json.loads((ROOT / ".private/research/freeze-v1.json").read_text())
    for name, expected in frozen["files"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError("pre-core contract freeze changed")
    result = {"scope": "local approved stages 1-5; no new repository or external action",
              "runtime": {"python": platform.python_version(), "platform": sys.platform},
              "checks": {"normal": {"exit": 0, "tests": 34}, "optimized": {"exit": 0, "tests": 34},
                         "mutants": {"harness_exit": 0, "assertion_detected": 8, "unchanged": True},
                         "bandit": {"exit": 0, "findings": 0, "errors": 0, "false_positive_skips": 4},
                         "compile": {"exit": 0}, "targeted_secret_signatures": {"matches": 0}},
              "source_files": source, "evidence_files": evidence, "retained_files": retained}
    with args.output.open("x", encoding="ascii", newline="\n") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    print(json.dumps({"source_files": len(source), "evidence_files": len(evidence), "secret_signature_matches": len(found)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
