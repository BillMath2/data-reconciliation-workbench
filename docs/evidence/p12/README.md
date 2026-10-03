# P12 local release evidence

This folder retains credential-free synthetic evidence from fresh local Compose
replays on October 2, 2026 (America/New_York; UTC timestamps extend into October 3).
Application baseline: P11 commit `901db40`, user-confirmed CI green. Capture and
documentation helpers are the uncommitted P12 working tree at capture time.
No new GitHub run or full expanded-AI release acceptance is claimed.

| File | Meaning |
|---|---|
| [rehearsal.json](rehearsal.json) | Full recording replay: owned project, step exit codes, start/completion, cleanup |
| [final-replay.json](final-replay.json) | Separate replay of setup/catalog/CLI/browser/cleanup without narration |
| [setup.json](setup.json), [setup-repeat.json](setup-repeat.json) | Nine migrations on empty SQL; zero pending on repeat |
| [health.json](health.json), [driver.json](driver.json) | Restricted runtime connectivity and SQL driver smoke result |
| [schema.json](schema.json) | Actual SQL catalog: columns, nullability, keys/indexes, migration ledger |
| [cli/recording.json](cli/recording.json) | Verified SQL demonstration with golden, correction, and no-op frames |
| [cli/golden-evidence.json](cli/golden-evidence.json) | Frozen original row/rule/reference evidence |
| [cli/corrected-evidence.json](cli/corrected-evidence.json) | Saved corrected publication evidence |
| [cli/repeat.json](cli/repeat.json) | Distinct no-op attempt reusing successful publication |
| [ui-verification.json](ui-verification.json) | Complete real-SQL browser verification and explicit checks |
| [recording.json](recording.json) | Narration, chapter timings, screenshot names, and mode disclosure |
| [media-qa.json](media-qa.json) | Encoded duration/dimensions, caption loading, chapter seeking, browser errors |
| [main-api-check.json](main-api-check.json) | Normal application still has 94/98 historical/current counts and six resolved findings |
| [unit-checks.txt](unit-checks.txt) | Host suite: 322 passed, 64 SQL skipped; separate from P11 full SQL suite |
| [provenance.json](provenance.json) | Baseline, retained file hashes, recording/tool scope, and open AI gate |

The recording contains actual SQL-backed browser actions and reading pauses.
Setup, archived P05A AI, and P11 recovery/query chapters are evidence exhibits,
not reruns of a provider call or backup. The screen investigation uses the offline
provider. Narration is locally synthesized using Microsoft David Desktop; it is
not Bill's voice. The [original narrative](../../release-narration.json) and
[captions](../../images/p12/captions.vtt) are retained with the
[MP4](../../images/p12/walkthrough.mp4).

The CLI, UI verification, and recording use separate fresh databases, so their
load IDs legitimately differ. All original captured data is synthetic. Tokens
are supplied only to local authentication and never appear on the recorded page.
No credential-bearing trace or raw environment file is retained. Raw WebM/WAV,
build logs, and unused previews stay under ignored `runs/`.

The catalog was checked on the fresh deployed schema, rather than inferred from
the migration source. The field dictionary documents every catalog column.
File hashes use raw bytes for images/video and UTF-8 text normalized to LF for
portable verification across Windows and Linux checkouts. The hash manifest
excludes itself and evolving prose; it checks retained evidence and delivered media.

Use the [replay guide](../../demo-guide.md) and [P12 validation](../../p12-validation.md).
The earlier full SQL suite and query/restore measurements remain in
[P11 evidence](../p11/README.md); P10's live/human review remains separate.
