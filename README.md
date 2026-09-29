# Data Reconciliation Workbench

An operational workbench for investigating why a source export and a report disagree. Python and SQL Server perform validation and reconciliation; an optional AI assistant explains the recorded evidence.

The planned demonstration follows **100 source rows → 94 accepted activities → 98/98 after source correction**. Every exclusion has a recorded reason, and repeating a successful load leaves counts unchanged.

## Watch the demonstration

Screenshots and a short recording will be the primary way to review this project. Capture begins when the CLI workflow is ready in P05; the web screen follows in P07. These materials are not available yet. The [demonstration guide](docs/demo-guide.md) defines what the recording will show.

## Project status

**P01 is complete; P02 is implemented locally.** Versioned source contracts, fixed validation-rule metadata, synthetic fixtures, a paginated mock registry API, and a department SQL seed script are now available. The ingestion pipeline, reconciliation workflow, AI integration, and workbench screen remain planned. Next is P03: application schema and migrations, after P02's new SQL/container checks pass in CI.

**P01 verification in GitHub Actions: 15 tests passed**, including both live SQL Server driver tests. See the [successful foundation run](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36504051164) and [P01 validation record](docs/p01-validation.md). **P02 local verification: 29 tests passed**, fixture reproduction matched all 29 generated files, and a real HTTP smoke test retrieved 25 unique projects. Four SQL tests are skipped locally; the new seed checks and container build changes await a new CI run.

## Run the foundation with Docker Compose

Use an x86-64 Docker host with Linux containers and Compose v2 or later. On Windows, Docker Desktop provides this environment. No native Python or SQL Server installation is required for this path.

From PowerShell in the repository:

```powershell
.\scripts\initialize-demo.ps1
docker compose --env-file .env.workbench up -d --wait --wait-timeout 240 sqlserver
docker compose --env-file .env.workbench build workbench
docker compose --env-file .env.workbench run --rm workbench health
docker compose --env-file .env.workbench run --rm workbench db-smoke
docker compose --env-file .env.workbench --profile test run --build --rm tests
docker compose --env-file .env.workbench down
```

The setup script creates `.env.workbench` with a generated demo password and preserves existing configuration. On other platforms, copy `.env.example` to `.env.workbench` and set a strong unique password before running the same Docker commands.

The database uses a named volume and stays inside the Compose network. `down` stops the containers and preserves that volume. The P01 CLI uses temporary tables only. With `--run-sql`, the P02 tests also create and remove a uniquely named disposable user database to test the source seed. Application tables and the workbench screen are not implemented. The Compose file accepts Microsoft's SQL Server Developer EULA for development use.

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
- **SQL verification:** health, parameter binding, Unicode, commit, and rollback checks against real SQL Server when enabled.
- **Automation:** GitHub Actions builds the images and runs the same Compose checks on pushes and pull requests; the foundation workflow has passed against real SQL Server.
- **Reproducibility:** uv lockfile, explicit configuration, synthetic-data scope, and a Docker build context that excludes credentials.

See the [implementation plan](docs/implementation-plan.md) for the remaining work, [development setup](docs/development.md) for tooling and troubleshooting, and [demonstration guide](docs/demo-guide.md) for the README/screenshot/recording sequence.
