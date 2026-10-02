# Demonstration and README guide

Status: P05 and P05A complete. The README links the [reviewed live explanation](evidence/p05a/live.txt) and labeled [offline stub](evidence/p05a/stub.txt). Verified SQL captures/replay are linked in the README; the original reports, evidence packets, transcript, and terminal recording are retained. The complete 5-7 minute narrated screen/AI recording remains a later deliverable.

The [33-second P05 replay](images/p05/walkthrough.gif) renders actual SQL output from [CI run 36637726571](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36637726571): golden discrepancy, corrected source, and no-op rerun. All three PNGs were visually inspected. PNGs are terminal-style renders, not desktop screenshots; the GIF changes reading pace, not the results. The [evidence bundle](evidence/p05/README.md) retains the real-time terminal `.cast`, transcript, reports, evidence JSON, recording manifest, test output, and provenance. The earlier [P04 replay](images/p04-baseline/walkthrough.gif) remains available as historical evidence. Follow the [reconciliation guide](reconciliation.md#record-the-sql-walkthrough) to reproduce the P05 recording.

## Review without installation

P07 adds an [actual browser preview](images/p07-preview/walkthrough.gif): 100/94 inspection, acknowledgement, corrected totals, retained resolved findings, and unchanged rerun. Its saved P05 facts and **simulated service/lifecycle** are explicitly documented in [capture provenance](evidence/p07/README.md). These are genuine screen captures but not new SQL execution evidence. CI now records the same journey against real SQL in the `ui-demo` artifact; P07 CI is user-confirmed green, with artifact retention still outstanding. See the [screen guide](workbench-ui.md).

The README is the entry point. Lead with the business problem, a linked recording thumbnail, and three screenshots showing the discrepancy, supporting evidence, and successful correction. Follow with a small architecture diagram, measured validation results, and the optional Compose quickstart.

Use synthetic data and keep configuration files, passwords, API keys, and unrelated desktop windows out of every capture. Add descriptive captions and alt text. Store screenshots under `docs/images/` when captured; link the recording once it exists. Do not add broken placeholder images or imply that a storyboard is a finished recording.

## Recording: 5-7 minutes

| Time | Show | Explain |
|---|---|---|
| 0:00-0:40 | Problem and three synthetic sources | Why a source count can disagree with a report |
| 0:40-1:20 | Compose services and database readiness | Separate application/database containers, a private network, persistent database volume, and a repeatable startup |
| 1:20-2:30 | Load the golden fixture; 100 source rows and 94 accepted activities | Two duplicate extras, three unknown projects, and one missing project ID account for all six exclusions |
| 2:30-3:30 | Exception detail and AI explanation | Calculations come from code; the assistant cites saved evidence and does not repair data |
| 3:30-4:40 | Correct the source and rerun | The corrected source and report both contain 98; historical findings remain available |
| 4:40-5:20 | Repeat the same load | A no-op rerun leaves totals unchanged |
| 5:20-6:30 | Actual CI results and recovery/tuning evidence | Real SQL Server tests, rollback, restore, and measured query improvement |

Show only implemented behavior. The initial P05 recording is a shorter CLI walkthrough; add the P05A explanation and P07 screen when ready. The final recording uses the complete flow above.

## Screenshot checklist

- **P05:** terminal output with 100/94, exclusion accounting, corrected 98/98, and no-op rerun.
- **P05A:** one actual provider explanation next to the evidence it cites; label offline stub output explicitly if shown separately.
- **P07:** workbench overview, one exception detail, and the corrected result.
- **P11:** measured query-plan improvement and successful recovery evidence.
- **P12:** select the clearest three product screenshots for the top of the README; link deeper engineering evidence below.

## Run it yourself

Docker Compose is the reproducibility path and part of the engineering demonstration. GitHub Actions runs the same container configuration for verification; it is not the demo website. A Codespaces walkthrough can be added later for remote interactive sessions, without making it necessary to view the README or recording. No hosted environment is required for the first portfolio release.
