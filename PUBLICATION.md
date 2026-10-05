# Publication review — October 5, 2026

Jake explicitly authorized public publication after review. This repository is a
curated source snapshot; original local histories and private/raw research records
remain preserved locally. Historical STATE/RESEARCH authorization statements describe
earlier stages and are superseded for this publication only.

Fresh audit: 34 unittest tests passed on Windows CPython 3.13.7.
Source review targeted input/output, execution boundaries and scanner findings.
Gitleaks reviewed current files; existing standalone histories were also scanned.
Three portfolio-wide scanner candidates were documentation prose, not credentials.
Bandit runtime-source results were reviewed separately from harness advisories.
These checks do not certify production security or untested environments.

CI preparation: Added pinned Windows tests/Bandit and scheduled Python CodeQL.
Hosted checks are a separate result; consult Actions for the current commit.
The local verification helpers can reference retained private evidence not shipped
here. Runnable application, public examples, unit tests and their frozen oracles
are included. Omitted raw evidence is not a claimed hosted test result.

AI assistance: Codex reviewed and prepared this publication. A bounded local
Ollama draft supported the overall overnight narrative; security judgments and
source verification remained with Codex.
