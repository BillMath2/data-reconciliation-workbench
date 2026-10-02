# Investigation evaluation, P10

`v1/spec.json` defines eighteen cases mapped to S01-S12, independently specified
numeric facts, required observed states, and a human rubric. Each case runs three
times. `v1/contexts/` contains synthetic evidence captured from real SQL Server,
not invented model answers. Two contexts are explicitly labeled adversarial
mutations of the S05 source record. SHA-256 checks bind each context to its case.

The application's fixed prompt and selected finding are the actual input under
test. The case rubric is **not** sent to the provider. There is no free-form user
question endpoint or separate evaluation-only explanation prompt.

## Run without a provider

```powershell
.venv\Scripts\python.exe -m workbench.evaluation --output runs/evals-offline
```

CI runs this command with the stub and exercises provider failures with mocks.
It needs neither a provider key nor paid calls. A fresh output directory is
required; results are never overwritten or automatically retried.

## Live evaluation

After authorization to send these synthetic contexts to OpenAI:

```powershell
.venv\Scripts\python.exe -m workbench.evaluation --provider openai --env-file .env --output runs/evals-live --budget-usd 3
```

The fixed model is `gpt-4.1-mini-2025-04-14`, using the application's Responses API
adapter with `store=false`, no tools, a bounded response, and no retries. The
runner reserves the full application maximum of $0.05 for every attempt:
54 attempts reserve $2.70. This is a conservative ceiling, not an observed bill.
Each batch requires a fresh directory and its own explicit budget. Interrupted
batches remain incomplete; they are not silently resumed or discarded.

Every response has automatic citation, fact, state, context-hash, and output
checks. Rejected provider output is retained only by this local evaluator for
review; it is not added to the web application's saved investigations. Inputs
must remain synthetic. Never point this recorder at production data.

The generated `human-review.md` contains each answer, rubric, and result hash.
Review **every repetition** against the linked context: citation membership does
not establish that a citation supports the prose. Check tentative causes,
source ownership, missing evidence, unsupported actions, and instruction
following. Record reviewer, verdict, and reasons. An automatic pass is never
human approval, and the runner never opens the expanded-assistant release gate.

## Regenerate SQL evidence

Start the existing SQL and mock-registry services, then run the two SQL capture
tests with an export directory mounted into the test container:

```powershell
docker compose --env-file .env.workbench --profile test run --build --rm --volume "${PWD}/runs/eval-capture:/app/eval-capture" -e WB_EVAL_CAPTURE_DIR=/app/eval-capture tests -q --run-sql tests/integration/test_evaluation_capture.py
```

The tests create and dispose only their randomly named test databases. They do
not alter the main workbench history. UUIDs and capture timestamps vary on replay;
fixture content, expected totals, rule selection, and deadline clock are fixed.
Compare results before replacing the versioned contexts and updating their
checksums/provenance. A material expectation change requires a new suite version.

S08 evaluates a dated prior publication. Missing-date freshness is separately
asserted with a fixed clock in SQL: a missing date has no saved reconciliation
and is not eligible for model investigation. S11/S12 model cases inspect the
retained publication after a failed refresh. Failure-specific causes absent from
that context must remain unknown. SQL tests also prove failed-attempt rejection,
rollback, retry/no-op, and existing registry API completeness behavior.

The methodology combines deterministic checks with manual semantic review,
consistent with [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
