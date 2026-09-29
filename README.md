# Data Reconciliation Workbench

An operational workbench for investigating why a source export and a report disagree. Python and SQL Server perform validation and reconciliation; an optional AI assistant explains the recorded evidence.

The planned demonstration follows **100 source rows → 94 accepted activities → 98/98 after source correction**. Every exclusion has a recorded reason, and repeating a successful load leaves counts unchanged.

## Watch the demonstration

Screenshots and a short recording will be the primary way to review this project. Capture begins when the CLI workflow is ready in P05; the web screen follows in P07. These materials are not available yet. The [demonstration guide](docs/demo-guide.md) defines what the recording will show.

## Project status

**P01 and P02 are complete. P03 has a corrective migration pending verification; P04 is implemented locally.** SQL, REST, and CSV ingestion now capture source evidence, quarantine invalid rows, and publish valid data through a restricted SQL login. Reruns, date replacement, audit events, and freshness checks are implemented. Reconciliation reports, the guided demo, AI integration, and the workbench screen remain planned.

**Current local checks: 110 tests passed; 33 SQL tests skipped.** P03's [CI run](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36572081104) passed database setup and runtime checks but found an identifier constraint rejecting valid hyphenated IDs (62 tests passed, 8 failed). Migration 004 addresses that defect; the next CI run must verify it together with P04. See [P03 findings](docs/p03-validation.md) and [P04 validation](docs/p04-validation.md). The last fully successful baseline is [P02](docs/p02-validation.md).

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

The [source-contract guide](docs/source-contracts.md) documents field ownership, manifests, fixture regeneration, the SQL seed, and S01-S12 scenario inputs. [Independent golden expectations](fixtures/expected/golden.json) specify the six excluded rows and expected totals. Local validation produces 94 accepted golden rows; SQL publication and correction assertions await CI. The reconciliation engine is P05 work.

## Engineering evidence

- **Docker:** separate runtime/test image targets, a non-root Python process, a pinned SQL Server image, readiness checks, private database networking, and persistent storage.
- **SQL engineering:** ten tables, source-row lineage, saved validation findings, atomic publication, an applied-version ledger, and a restricted runtime role. Integration tests cover migration rollback, permissions, reruns, and correction; live verification is pending.
- **Automation:** GitHub Actions builds the images and runs the same Compose checks on pushes and pull requests. The latest SQL failure and its pending correction are documented above.
- **Reproducibility:** uv lockfile, explicit configuration, synthetic-data scope, and a Docker build context that excludes credentials.

See the [implementation plan](docs/implementation-plan.md) for the remaining work, [development setup](docs/development.md) for tooling and troubleshooting, and [demonstration guide](docs/demo-guide.md) for the README/screenshot/recording sequence.
