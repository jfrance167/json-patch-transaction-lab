# JSON Patch transaction lab

A standard-library learning tool for ordered changes to supplied synthetic JSON values. It demonstrates six operations, array index shifts, test preconditions, detached copying and rollback of the entire private working value on failure. It never patches a resource or configuration.

The demo starts with q=2, privately replaces it with3, then tests for2. That test fails; the report returns the original q=2, records one completed attempt, failure at index1 and the final remove as not-run. Input and operation values remain unchanged.

## Run

Verified locally on Windows CPython3.13.7. No installation or dependencies needed. Run from this directory:

```powershell
python -m patch_lab samples/demo.json
python -m patch_lab samples/demo.json --output fresh-report.json
python -m scripts.demo_reports --output another-fresh-report.json
```

The demo intentionally exits **4**, meaning a complete rejected-patch report, not a program crash. `samples/demo-report.json` is a saved example. Fresh output names must not exist; existing files and input aliases/hardlinks are refused.

| Exit | Meaning |
|---|---|
|0|Applied, final value unchanged|
|1|Applied, final value changed|
|4|Complete rejected-patch report; original result preserved|
|2|Invalid input, limit, argument or delivery failure|
|3|Unknown schema after full common/profile admission|

Minimal input:

```json
{"schema":"json-patch-lab/1","target":{"q":2},"operations":[{"op":"test","path":"/q","value":2},{"op":"replace","path":"/q","value":3}]}
```

## Behavior and architecture

`patch_lab.contract.parse(bytes)` checks strict UTF-8, lexical depth/numbers, duplicate decoded names and full admission. `patch_lab.model.analyze(envelope)` repeats complete native admission and returns `(detached_report, exit_code)`. Invalid/unsupported inputs raise fixed LabError/Unsupported. `render` serializes only admitted model reports/fixed diagnostics; it is not admission for arbitrary supplied reports. Checked CLI handles file observations, fresh output and sink failures.

Operations run sequentially against the current private value. Add inserts/replaces a member or array element and can replace root; remove/replace require existing locations; copy snapshots current source before add; move resolves source then removes and evaluates destination afterward; test uses recursive JSON types, so false differs from0. Object order is irrelevant; array order matters. Any operation or working-resource failure discards the whole private result; trace records completed local attempts, the first failed step and not-run suffix. This is not a persistent transaction log.

Plain pointers address root with empty string, preserve empty names and exact Unicode, and decode tilde escapes once in the required order. Numeric-looking object names are ordinary keys. Arrays require ASCII unsigned indices without leading zeros; `-` means append only at an add-like final array destination. Missing parents are never created; strings/scalars are never traversed as arrays. Move forbids decoded-token source ancestry, checks existence before an equal-path no-op, and uses post-removal indices. Root removal is excluded explicitly; every result remains a JSON value. Unknown operation members are ignored semantically after validation, including their complete nested values.

## Bounds and security model

PLAN.md freezes exact admission and report limits:64KiB raw input,≤16 operations, target/meaningful values≤512 nodes/depth7, global4096 nodes/depth10, accepted working values≤1024 nodes/128 containers/depth7 and128KiB ASCII report including LF. Exact builtins only, no deepcopy/subclass/metaclass hooks; cyclic input rejected and shared acyclic values counted each occurrence. Integer-only subset within±9007199254740991; fractions/exponents/nonfinite/-0 rejected on encoded input. Native values cannot recover original spelling. Strings reject surrogates/noncharacters while retaining admitted invisible/control/private/unassigned code points exactly.

Each operation has a bounded temporary candidate that is checked before reuse. Repeated copies cannot continue after the working cap. Temporary allocation is not a preallocation rejection guarantee. Reports echo synthetic target/operations/result with independent mutable snapshots; private/employer/client data is excluded. Fixed diagnostics omit supplied values, paths and OS details.

The actual fifth-copy fixture reaches1207 nodes after four accepted candidates ending at1006; it rejects at index4 and restores the original202-node value. A62,258-byte admitted literal UTF-8 input expands to186,804-byte ASCII report; renderer rejects before output/file creation at131,072. This is measured finite growth, not an unrestricted exponential claim. Windows stdout is configured for LF to avoid post-cap CRLF expansion. Partial physical output and hostile races remain possible; no atomic-file/HTTP-server guarantee.

## Verification and learning

34 tests pass normally and under optimization, no skips;61 complete original reports and10 diagnostics frozen before core. Actual CLI covers every report/diagnostic; eight assertion mutants detect rollback, index order, equality, copy alias, ancestry, parent creation and genuine node/output caps. Bandit1.9.4 runtime/demo:456 LOC, zero remaining findings/errors, four documented rule-specific B105 annotations. ECC self-review fixed Windows stdout translation and strengthened full serialized oracle checks; failures preserved. See VALIDATION.md, REVIEW.md and private final receipt for exact evidence. No independent audit, hosted CI, other Python/platform, full RFC/general-JSON conformance or production assurance.

MIT original product code; NOTICE.md documents owned adaptations, AI assistance and separate inert upstream research licenses. No upstream vectors/code installed or executed. Source research and limitations are in RESEARCH.md; consequential choices and exercises in DECISIONS.md/LEARNING.md. No repository or public action under this lab's approved scope.

Optional exercise: predict moving index1 to3 in a four-element array, then explain why a later failed test must return the original array even though the trace shows a completed move.

## Publication status

See [publication review](PUBLICATION.md) for the October 5 source snapshot, fresh local checks, evidence boundaries and current hosted-check distinction.
