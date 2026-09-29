# Data Reconciliation Workbench

An operational workbench for investigating why a source export and a report disagree. Python and SQL Server perform validation and reconciliation; an optional AI assistant explains the recorded evidence.

The planned demonstration follows **100 source rows → 94 accepted activities → 98/98 after source correction**. Every exclusion has a recorded reason, and repeating a successful load leaves counts unchanged.

## Watch the demonstration

Screenshots and a short recording will be the primary way to review this project. Capture begins when the CLI workflow is ready in P05; the web screen follows in P07. These materials are not available yet. The [demonstration guide](docs/demo-guide.md) defines what the recording will show.

## Project status

**P01 is in progress.** The repository now contains a Python CLI, validated configuration loading, driver smoke tests, locked dependencies, a Dockerfile, Docker Compose, and a GitHub Actions workflow. The ingestion pipeline, reconciliation workflow, AI integration, and web screen are not implemented yet.

Local verification: **13 unit tests pass; 2 SQL integration tests are skipped** pending a running database. Docker image builds, live SQL checks, and the GitHub Actions run remain unverified. See [development setup](docs/development.md) for the acceptance gate.

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

The database uses a named volume and stays inside the Compose network. `down` stops the containers and preserves that volume. P01 uses temporary tables only; it does not create application tables or serve a web page. The Compose file accepts Microsoft's SQL Server Developer EULA for development use.

## Engineering evidence

- **Docker:** separate runtime/test image targets, a non-root Python process, a pinned SQL Server image, readiness checks, private database networking, and persistent storage.
- **SQL verification:** health, parameter binding, Unicode, commit, and rollback checks against real SQL Server when enabled.
- **Automation:** GitHub Actions builds the images and runs the same Compose checks on pushes and pull requests; the workflow has not been run yet.
- **Reproducibility:** uv lockfile, explicit configuration, synthetic-data scope, and a Docker build context that excludes credentials.

See the [implementation plan](docs/implementation-plan.md) for the remaining work, [development setup](docs/development.md) for tooling and troubleshooting, and [demonstration guide](docs/demo-guide.md) for the README/screenshot/recording sequence.
