# Local verification

Windows CPython3.13.7, Bandit1.9.4. No installs, upstream execution or remote inference.

| Check | Exact local outcome | Evidence under .private/verification |
|---|---|---|
|python -m unittest discover -v|PASS0,34 tests,no skips|final-normal.log|
|python -O -m unittest discover -v|PASS0,34 tests,no skips; optimized actual children|final-optimized.log|
|Eight assertion mutants|PASS harness0;8 process exits1 with one assertion failure each; originals unchanged|mutations-final-after-review/summary.json and */result.log|
|python -m compileall -q patch_lab tests scripts|PASS0|compile.log|
|Bandit runtime/demo|PASS0,456 LOC,zero findings/errors,four narrow B105 annotations|bandit-final-after-review.json/log|
|61 full original reports/10 fixed diagnostics|Frozen before application code; fixture SHA256 unchanged|../research/freeze-v1.json, resource-construction.json and fixtures/oracles.json|
|Measured actual admission/model/renderer|62,258 raw bytes admitted;186,804 ASCII report bytes rejected at131,072; fifth copy rejects1207 nodes after1006|amplification.json|
|Source/evidence receipt|Generated after docs and independently rehashed|final-receipt.json,receipt-rehash.json|

Original fixture SHA256:7803075b3316b3311386d674bd1a377eb749669857bb1e13d516db7090fc7cd0. Freeze binds PLAN, authoring source, fixture and independent resource construction. Full expected reports include limits,target,operations,result,type,status,change,prefix count,failed index and every trace row; outcomes supplied before engine. Secondary boundary/alias/mutant tests are not counted as independent frozen reports. No upstream/RFC vectors adopted.

Actual processes verify all61 report JSON values and exact sorted ASCII+LF bytes and all10 diagnostics. Tests cover help/misuse/fresh/existing/empty/NUL/input aliases/hardlinks, actual closed stdout/stderr/both/help/error readers using a stdin barrier, simulated dirty/short/flush/close sinks and observed metadata changes. Physical close failure is simulated, pipes actual. Input remains unchanged; output-cap failure creates no report/file. Exclusive writes are not atomic or hostile-race proof.

Feasible limits exercise raw65536/65537, early numeric/depth decoder gating, tree nodes/depth/containers/text, global operation/nodes/text, meaningful values, pointers/tokens, working nodes/containers/depth/text and report cap. UTF8 four-times-scalar bounds and several global/result bounds are conservative/redundant; no inaccessible overflow claim. Candidate allocation ≤2048 nodes/256 containers/8192 text scalars/32768 text UTF8 bytes/depth15 before checking;≤16 operations; not preallocation rejection. Peak retained input/working/candidate/source/report copies add finite declared budgets; these are logical counts, not measured process RSS.

Actual raw62,258 fits65536; global164 nodes/18 containers/15582 scalars/61662 text UTF8 bytes, peroperation20 nodes/2 containers/1943 scalars/7703 textbytes. Independent counts were frozen before core. Fifth-copy sequence202,403,604,805,1006,1207 nodes rejects index4; remaining test not-run and original202-node result returned. Node-cap1024→2048 and report-cap131072→262144 mutants miss genuine rejection and fail their targeted assertions without comparing changed limits metadata. Copy-alias mutant targets the private admitted helper and complements public detached snapshot tests. No exponential/unbounded growth claim.

Preserved failures: stage2 supplemental budget-count error and exact-byte stdout CRLF review failures in both modes, followed by focused fixes and final reruns. Initial v1 suites/mutations/scan and pre-final mutation evidence remain historical, not current acceptance. ECC self-review scope/fix and rule-specific scanner false positives are in REVIEW.md. Targeted credential signatures have narrow coverage; no full secret/history scanner, own Git repo, hosted CI, other platform/runtime, full conformance or independent audit claim.
