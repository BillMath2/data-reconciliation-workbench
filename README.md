# Data Reconciliation Workbench

An operational workbench for investigating why a source export and a report disagree. Python and SQL Server perform validation and reconciliation. An optional CLI assistant explains saved evidence, with an offline stub and a reviewed live example.

The verified SQL demonstration follows **100 source rows → 94 accepted activities → 98/98 after source correction**. Every exclusion has a recorded reason, and repeating a successful load leaves counts unchanged.

## Watch the demonstration

[![Recorded SQL reconciliation: 100 source rows, 94 accepted, two duplicate extras and four invalid rows](docs/images/p05/step-1.png)](docs/images/p05/walkthrough.gif)

**[Watch the 33-second SQL walkthrough](docs/images/p05/walkthrough.gif)** — actual CLI output from [successful P05 CI run 36637726571](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36637726571), rendered as terminal captures with reading pauses. It shows the discrepancy, corrected source, and unchanged rerun. [Recording provenance](docs/evidence/p05/provenance.json) records the commit, supplied artifact links, and file hashes. This is a paced output replay, not desktop video.

| Recorded stage | Verified result |
|---|---|
| [Discrepancy](docs/images/p05/step-1.png) | 100 source rows, 94 accepted; two duplicates, three unknown projects, and one missing project ID explain all six exclusions |
| [Source correction](docs/images/p05/step-2.png) | Source and report agree: 98 completed activities and 197 units |
| [Identical rerun](docs/images/p05/step-3.png) | No-op; the same publication and totals are reused |

Inspect the [saved evidence and terminal recording](docs/evidence/p05/README.md), reproduce the [demo commands](docs/reconciliation.md#record-the-sql-walkthrough), or follow the [demonstration guide](docs/demo-guide.md).

## Project status

**P01-P05 and P05A are complete; P06 is implemented locally and awaits SQL/API acceptance.** The reconciliation report groups exclusions by their primary reason, preserves unknown totals, and saves a bounded evidence packet with each publication. Historical reports survive source correction. The first CLI AI explanation and local evidence API are available; the workbench screen remains P07. See [P06 validation](docs/p06-validation.md).

**Verified P05 SQL suite: [164 tests passed](docs/evidence/p05/sql-checks.txt), including all 38 SQL cases, with no skips.** Both CI jobs were confirmed green; the downloaded artifacts were reviewed on October 1, 2026. See [P05 validation](docs/p05-validation.md) for provenance and checks, and [P04 verification](docs/p04-validation.md) for the earlier baseline.

## Explain the discrepancy

[Read the reviewed live AI explanation](docs/evidence/p05a/live.txt) alongside its [saved SQL evidence](docs/evidence/p05/golden-evidence.json), or try the explicitly labeled offline stub without SQL or an API key:

```powershell
.\scripts\uv.ps1 run --locked workbench explain --packet docs/evidence/p05/golden-evidence.json --provider stub --format text
```

Code checks the answer's structured counts and citations. The assistant has no database credentials, tools, or repair path; when AI is unavailable, deterministic evidence and guidance remain visible. Live prose still requires review. See the [assistant guide](docs/assistant.md) for setup and limits, and [P05A validation](docs/p05a-validation.md) for the single accepted example and tests. Current local suite: **158 passed, 38 SQL tests skipped**; the user confirmed the expanded P05A CI run green for commit `59091f3`. The verified P05 SQL baseline above remains distinct.

## Inspect evidence through the API

P06 adds authenticated report/evidence inspection and operator acknowledgement, with resolution linked to successful source correction. The API exposes the original saved packets and keeps lifecycle state separate. It includes local demo identities and CSRF protection; the web screen comes next. See the [API setup and endpoint guide](docs/evidence-api.md). Local verification: **195 passed, 44 SQL tests skipped**; migration 007 and the live API checks still need CI acceptance.

## Run the foundation with Docker Compose

Use an x86-64 Docker host with Linux containers and Compose v2 or later. On Windows, Docker Desktop provides this environment. No native Python or SQL Server installation is required for this path.

From PowerShell in the repository:

```powershell
.\scripts\initialize-demo.ps1
docker compose --env-file .env.workbench up -d --wait --wait-timeout 240 sqlserver
docker compose --env-file .env.workbench build workbench
docker compose --env-file .env.workbench --profile tools run --build --rm migrate
docker compose --env-file .env.workbench run --rm workbench health
docker compose --env-file .env.workbench run --rm workbench db-smoke
docker compose --env-file .env.workbench --profile test run --build --rm tests
docker compose --env-file .env.workbench down
```

The setup script creates or upgrades `.env.workbench` with distinct generated administrator and runtime passwords, preserving existing nonempty credentials. On other platforms, copy `.env.example` to `.env.workbench` and set both passwords to different strong values (16-128 characters for the runtime password) before running the same Docker commands.

The `migrate` service creates the `workbench` database, applies pending migrations, and provisions the restricted `workbench_app` login. Rerunning it leaves applied migrations unchanged. The regular `workbench` service uses that runtime login. See the [schema and migration guide](docs/database-schema.md).

The database uses a named volume and stays inside the Compose network. `down` stops containers and preserves that volume. SQL tests create and remove their own uniquely named disposable databases and start the mock registry. Setup leaves the application tables empty; follow the [ingestion guide](docs/ingestion.md) to seed and load them. There is no workbench screen yet. The Compose file accepts Microsoft's SQL Server Developer EULA for development use.

## Inspect the synthetic sources

```powershell
.\scripts\uv.ps1 sync --locked --python 3.12
.\scripts\uv.ps1 run --locked workbench-fixtures --check fixtures/generated
.\scripts\uv.ps1 run --locked workbench-registry
```

The registry serves `http://127.0.0.1:8001/projects` with stable pagination. For the container version, use `docker compose --env-file .env.workbench --profile sources up -d --build --wait mock-registry`.

The [source-contract guide](docs/source-contracts.md) documents field ownership, manifests, fixture regeneration, the SQL seed, and S01-S12 scenario inputs. [Independent golden expectations](fixtures/expected/golden.json) specify the six excluded rows and expected totals. P04's SQL tests verified 94 accepted rows/189 units, then 98 rows/197 units after correction. P05 adds persisted reconciliation and the [read-only report/evidence commands](docs/reconciliation.md).

## Engineering evidence

- **Docker:** separate runtime/test image targets, a non-root Python process, a pinned SQL Server image, readiness checks, private database networking, and persistent storage.
- **SQL engineering:** eleven tables and three reporting views, source-row lineage, saved findings/reconciliation, atomic publication, an applied-version ledger, and a restricted runtime role. P05's schema and rollback checks passed in the SQL suite; P06 lifecycle migration 007 and its new checks await CI.
- **Automation:** GitHub Actions builds the images, tests real SQL Server, and captures the guided SQL demo with its evidence packets and media.
- **Reproducibility:** uv lockfile, explicit configuration, synthetic-data scope, and a Docker build context that excludes credentials.

See the [implementation plan](docs/implementation-plan.md) for the remaining work, [development setup](docs/development.md) for tooling and troubleshooting, and [demonstration guide](docs/demo-guide.md) for the README/screenshot/recording sequence.
