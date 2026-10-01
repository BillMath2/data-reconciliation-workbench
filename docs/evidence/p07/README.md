# P07 browser preview provenance

These are actual Chromium captures of the implemented screen, produced by `scripts/check-ui.py --fixture` on October 1, 2026. **They use an in-memory service, not SQL Server.** Report counts/source facts come from the accepted P05 packets in `docs/evidence/p05/`; acknowledgement, resolution, freshness clock, and attempt states are simulated by `tests/e2e/fixture_service.py`.

The [verification manifest](verification.json) records the mode and passing browser checks. The [capture hashes](capture-hashes.json) identify the retained files. These preview artifacts must not be cited as proof that P07's new SQL/browser gate passed.

| Capture | What the browser displays |
|---|---|
| [Golden discrepancy](../../images/p07-preview/01-golden.png) | 100/94 report and captured source inspection |
| [Reviewed finding](../../images/p07-preview/02-reviewed.png) | Acknowledged, still unresolved |
| [Corrected result](../../images/p07-preview/03-corrected.png) | 98/98 activities, 197/197 units |
| [Retained history](../../images/p07-preview/04-resolved.png) | Six resolved findings linked to the correcting publication |
| [Unchanged rerun](../../images/p07-preview/05-rerun.png) | No-op reuse with unchanged totals |
| [Missing date](../../images/p07-preview/06-missing-date.png) | Empty evidence and overdue feed for the selected date |
| [Mobile screen](../../images/p07-preview/07-mobile.png) | Responsive layout; the exception table can scroll horizontally |

The [25-second walkthrough](../../images/p07-preview/walkthrough.gif) is a paced replay of the first five actual screenshots, with no narration; it is not continuous screen video. P12's final 5-7 minute narrated recording remains outstanding.

CI is configured to upload a separate `ui-demo` artifact from the real SQL-backed journey. After it passes, retain its run URL, inspected test output, verification manifest, and screenshots; replace these explicitly labeled previews in the README with that accepted evidence.
