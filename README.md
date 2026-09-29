# Data Reconciliation Workbench

An operational workbench for investigating why a source export and a report disagree. Python and SQL Server perform validation and reconciliation; an optional AI assistant explains the recorded evidence.

The planned demonstration follows **100 source rows → 94 accepted activities → 98/98 after source correction**. Every exclusion has a recorded reason, and repeating a successful load leaves counts unchanged.

## Watch the demonstration

Screenshots and a short recording will be the primary way to review this project. Capture begins when the CLI workflow is ready in P05; the web screen follows in P07. These materials are not available yet. The [demonstration guide](docs/demo-guide.md) defines what the recording will show.

## Project status

**P01 and P02 are complete; P03 is implemented locally and awaits SQL CI verification.** The foundation now includes source contracts and fixtures, a mock registry API, eight SQL tables, transactional migrations, and separate setup/runtime database credentials. The ingestion pipeline, reconciliation workflow, AI integration, and workbench screen remain planned.

**P02 verification in GitHub Actions: 33 tests passed**, including all four SQL checks, plus the mock registry container check. See the [successful P02 run](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36508588521) and [validation record](docs/p02-validation.md). **P03 local verification: 53 tests passed; 17 SQL tests skipped.** Lint, formatting, fixture reproduction, and Compose configuration validation passed. New migrations, permissions, and container execution require the next CI run; see [P03 validation](docs/p03-validation.md).

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

The database uses a named volume and stays inside the Compose network. `down` stops containers and preserves that volume. SQL tests create and remove their own uniquely named disposable databases; the application tables remain empty until ingestion is implemented in P04. There is no workbench screen yet. The Compose file accepts Microsoft's SQL Server Developer EULA for development use.

## Inspect the synthetic sources

```powershell
.\scripts\uv.ps1 sync --locked --python 3.12
.\scripts\uv.ps1 run --locked workbench-fixtures --check fixtures/generated
.\scripts\uv.ps1 run --locked workbench-registry
```

The registry serves `http://127.0.0.1:8001/projects` with stable pagination. For the container version, use `docker compose --env-file .env.workbench --profile sources up -d --build --wait mock-registry`.

The [source-contract guide](docs/source-contracts.md) documents field ownership, manifests, fixture regeneration, the SQL seed, and S01-S12 scenario inputs. [Independent golden expectations](fixtures/expected/golden.json) specify the six excluded rows and expected totals; these describe the future pipeline result, not an already implemented reconciliation engine.

## Engineering evidence

- **Docker:** separate runtime/test image targets, a non-root Python process, a pinned SQL Server image, readiness checks, private database networking, and persistent storage.
- **SQL engineering:** eight-table schema, source-row lineage, relational constraints, transactional migration ledger, and a restricted runtime role. New integration tests cover migration rollback and permissions; live P03 verification is pending.
- **Automation:** GitHub Actions builds the images and runs the same Compose checks on pushes and pull requests; the foundation workflow has passed against real SQL Server.
- **Reproducibility:** uv lockfile, explicit configuration, synthetic-data scope, and a Docker build context that excludes credentials.

See the [implementation plan](docs/implementation-plan.md) for the remaining work, [development setup](docs/development.md) for tooling and troubleshooting, and [demonstration guide](docs/demo-guide.md) for the README/screenshot/recording sequence.
