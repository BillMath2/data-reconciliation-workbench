# P10 local evidence

Verified October 2, 2026, on the working tree based on `67f7f78`.
P09 green CI was confirmed by the user; P10 CI is not yet confirmed.

- `sql-checks.txt`: full Docker/SQL suite, 368 passed, 54 SQL cases, no skips.
- `focused-sql-checks.txt`: 13 passing tests for the final evidence lookup, corpus capture, and API/persistence recheck.
- `offline-batch.json` and `offline-results.json`: 18 contexts, three stub
  repetitions each; 54 automatic passes. These are not live-model evidence.
- `browser-verification.json`: Chromium walkthrough with explicit simulated
  evidence/persistence; not a new SQL-backed browser recording.
- `tested-source-sha256.json`: fingerprints of the final implementation and corpus.

The [versioned contexts](../../../evals/v1/contexts) were captured from real SQL
test databases containing only generated fixtures. Two source-injection cases
are labeled synthetic mutations. The [capture provenance](../../../evals/v1/provenance.json)
records fixture and context hashes; generated SQL IDs and timestamps are retained.

No live P10 calls have run: automatic approval review requires explicit approval
of this payload and the OpenAI destination. The pending request covers 54 calls,
with a $2.70 reserved maximum inside the announced $3 cap. Credentials are absent
from this evidence. Human review and green CI are separate remaining gates.
