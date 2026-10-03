# P10 validation: assistant scenarios and failure behavior

Status: implemented and locally verified; live evaluation authorization and human
semantic review remain open; GitHub CI was user-confirmed green for `47a79fb` after a rerun, October 2, 2026.
P09 is accepted on the user's green CI confirmation for commit `67f7f78`;
the exact CI run URL/artifacts were not independently inspected in this session.

## Implemented

- Eighteen versioned evaluation contexts covering S01-S12, the composite golden
  discrepancy, and two source-text prompt injections. Real SQL capture and
  independent expected facts are separated from model output.
- Three repetitions per case, fixed provider/model/prompt metadata, context and
  result hashes, latency, bounded cost, no automatic retries, preserved failures,
  and a human review worksheet. Paid evaluation is separate from ordinary CI.
- Deterministic failures for fabricated counts, unknown citation IDs, repair
  claims, tool-call output, timeout, and unavailable provider. Facts and guidance
  survive these failures without a provider action path.
- Duplicate investigations now capture the accepted original row alongside the
  excluded copy. Unknown-project investigations include matching captured
  registry records from the same fixed reference set, exposing the rejected
  project's department dependency. Existing saved packets remain immutable.

## Verification

The SQL capture tests passed against Docker SQL Server in two disposable databases.
All **54 offline evaluation repetitions passed**. The full Docker suite passed
**368 tests, including all 54 SQL cases, with no skips**, in 227.49 seconds.
The host test run separately passed 314 tests with 54 SQL skips. Both runs have
the existing Starlette/httpx deprecation warning.

After the final normalized reference-key adjustment, all **13 focused SQL evidence,
API, and investigation tests passed** again.

The Chromium fixture walkthrough, lint, formatting, deterministic fixture
checks, and `git diff --check` passed. No dependency, schema migration, provider
model, or prompt change was required. The provider adapter only gained an
evaluation-only response observer; the screen does not retain raw responses.

See [retained verification evidence](evidence/p10/README.md) and
[corpus provenance](../evals/v1/provenance.json).

## Acceptance gates

The expanded assistant is not yet accepted. Automatic approval review blocked
live submission because it requires explicit authorization for sending the
specified synthetic SQL-derived contexts to OpenAI. No live P10 call has run.
The pending request names the payload, destination, 54 calls, and $2.70 reserved
ceiling. It does not affect deterministic workbench operation or offline tests.

After authorization, retain every real answer and review each causal assertion
against its supplied evidence; no model judge substitutes for a human reviewer.
Any failed case blocks expanded assistant release. GitHub CI is now user-confirmed green for `47a79fb` after a rerun. The exact run artifacts were not independently inspected. This clears the CI checkpoint, not the live/human-review gates.

See [evaluation instructions and scenario boundaries](../evals/README.md).
P11 recovery/performance work remains independent of the expanded assistant gate.
