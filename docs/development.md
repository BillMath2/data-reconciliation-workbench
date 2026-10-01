# Foundation development setup

## P01 acceptance status

Implemented: Python 3.12 package, CLI entry point, configuration validation, redacted CLI errors, uv lockfile, unit tests, opt-in SQL integration tests, Docker runtime/test targets, Compose database readiness, and a GitHub Actions workflow.

P01 verification on Windows: Python 3.12.14, uv 0.12.20, mssql-python 1.15.0 import, lint/format checks, and 13 passing unit tests. Local runs skip SQL integration tests unless explicitly enabled against a running database.

**P01 is complete.** [GitHub Actions run 36504051164](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36504051164), for commit `5552a3b`, built both images, started SQL Server, passed `config-check`, `health`, and `db-smoke`, and passed all 15 tests with `--run-sql`. The `sql-checks` artifact confirms zero skipped integration tests in that run. See the [validation record](p01-validation.md).

The container execution was verified on GitHub's Ubuntu runner. Docker Desktop and native SQL Server have not been installed as part of this work; local container execution is not claimed. A Docker host is needed to repeat the Compose demonstration locally.

**P02 is complete:** [run 36508588521](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36508588521) passed all 33 tests, including four live SQL checks, and verified the mock registry container. See [P02 validation](p02-validation.md) and [source contracts and fixture commands](source-contracts.md).

**P01-P05 are complete:** P05 run 36637726571 passed **164 tests, including all 38 SQL cases with no skips**. Its downloaded demo and test artifacts were inspected, and the README links the verified golden/correction/no-op replay and saved evidence. P05A now adds the CLI assistant and a reviewed live example: 158 local tests pass, with 38 SQL tests skipped; the expanded CI run is pending. See [assistant setup](assistant.md) and [P05A validation](p05a-validation.md). See [P04 verification](p04-validation.md), [P05 validation](p05-validation.md), and [reconciliation commands](reconciliation.md). One upstream Starlette TestClient deprecation warning remains.

## Container setup

Use an x86-64 Docker host with Linux containers, Compose v2 or later, and sufficient memory for SQL Server plus the Python container; allocate at least 4 GB for this development stack. Microsoft's SQL Server container support is Linux x86-64; ARM emulation is not a verified setup for this repository. See [Microsoft's container guide](https://learn.microsoft.com/en-us/sql/linux/install-upgrade/quickstart-install-docker?view=sql-server-ver17).

Follow the Compose commands in the [README](../README.md). The SQL image is pinned to the official `2022-latest` digest resolved on 2026-09-28. Refresh the digest deliberately and rerun SQL tests when updating it. SQL readiness uses a real query with `sqlcmd`; dependent services wait for the database to become healthy, as described in [Docker's startup-order guidance](https://docs.docker.com/compose/how-tos/startup-order/).

Configuration:

| Setting | Meaning |
|---|---|
| `WB_SQL_PASSWORD` | Administrator password in the Compose env file; password of the configured login for direct Python use |
| `WB_SQL_RUNTIME_PASSWORD` | Separate runtime password, 16-128 characters; required by Compose and `db-setup`; never commit either password |
| `WB_SQL_SERVER` | Host/port for direct Python use; Compose explicitly sets `sqlserver,1433` |
| `WB_SQL_DATABASE` | Target database for direct Python; Compose pins setup/runtime to `workbench` and tests to `master` |
| `WB_SQL_USERNAME` | Login for direct Python; Compose uses `sa` for setup/tests and `workbench_app` for runtime |
| `WB_SQL_DRIVER` | `mssql-python`, or explicitly selected `pyodbc` fallback |
| `WB_SQL_TRUST_CERTIFICATE` | `true` for this self-signed development container; encryption remains enabled |
| `WB_SQL_CONNECT_TIMEOUT` | Connection/query timeout in seconds, from 1 to 30 |

The Compose environment overrides connection settings to target its own database. The `migrate` service receives administrator credentials and the runtime password for provisioning; the `workbench` service receives only the runtime password as its `WB_SQL_PASSWORD`. Test containers use administrator access to create isolated databases. Run the setup service before runtime checks, as shown in the README.

For routine shutdown, use `docker compose --env-file .env.workbench down`. The database remains in `sql-data`. Changing the environment password does not change an existing database's password; retain the original credential or follow an explicit database reset procedure. Avoid deleting volumes merely to stop the demo.

If a check fails, first inspect `docker compose --env-file .env.workbench ps` and database readiness. Review database logs locally if necessary, and keep credentials out of shared logs/screenshots. `workbench` deliberately withholds raw driver errors, since those may contain connection details.

## Python development without running SQL

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it is not available. The PowerShell wrapper also recognizes an ignored portable uv installation in `.tools/uv/`; caches and downloaded Python stay inside this workspace.

```powershell
.\scripts\uv.ps1 sync --locked --python 3.12
.\scripts\uv.ps1 run --locked ruff check .
.\scripts\uv.ps1 run --locked ruff format --check .
.\scripts\uv.ps1 run --locked pytest -q
.\scripts\initialize-demo.ps1
.\scripts\uv.ps1 run --locked workbench --env-file .env.workbench config-check
```

On Linux/macOS use the corresponding `uv` commands directly. Unit tests run without a database. `config-check` checks configuration only; it does not prove SQL connectivity. The Compose server name is resolvable inside Compose, so run SQL checks inside the container unless using a separately configured database endpoint.

Commands return JSON and exit with 0 for success, 2 for invalid configuration/arguments, 3 for unavailable drivers or failed SQL operations, 4 for safe preflight/migration/bootstrap diagnostics, and 5 for recorded failed ingestion attempts. No environment file is loaded implicitly. `--env-file` explicitly opts into a file; process variables override its values. The existing root `.env` is left untouched.

## Live SQL checks and driver fallback

`health` executes a read-only round trip. `db-smoke` binds text containing Unicode, quotes, and punctuation; commits one row to a session-local temporary table; rolls back a second row; and verifies that only the committed row remains. The temporary table disappears when the connection closes. No application data is modified.

The Compose test service passes `--run-sql`, so missing or failing SQL access fails the tests instead of silently skipping them. The default local pytest invocation clearly reports SQL tests as skipped.

P02's additional integration tests create and later remove a uniquely named disposable user database for the department seed. They test repeatability, rejection of changed reference data, and refusal to seed system databases. Run them only with credentials authorized to create a test database; they do not seed the configured application's database.

P03's tests also create and remove isolated `workbench_schema_test_<uuid>` databases. They verify migration reapplication is a no-op, a failed migration rolls back its DDL and ledger row, older migration sets are rejected, source seed data survives migration, business keys and lineage FKs hold, publication uniqueness holds, and the runtime role permits pipeline writes while rejecting DDL/source/ledger changes. These tests must pass on real SQL Server before P03 is complete.

P04's integration tests require `WB_SQL_RUNTIME_PASSWORD` as well as the administrator connection. They migrate and seed isolated databases, provision the restricted login, then run ingestion with that login against real SQL and the registry HTTP service. The Compose test profile starts both dependencies. Direct Python runs also need a running registry at `WB_TEST_REGISTRY_URL` (default `http://127.0.0.1:8001/projects`). Tests verify rollback, no-op history, partition replacement, source failures, reference dependencies, and freshness. They do not modify the configured application database.

If `mssql-python` blocks progress, install the optional Python fallback with `uv sync --locked --extra odbc`, install Microsoft ODBC Driver 18 on the execution host, and explicitly set `WB_SQL_DRIVER=pyodbc` for direct Python checks. Repeat the same live smoke tests before choosing the fallback. The default Docker image currently contains the primary driver only; adopting the fallback there also requires updating its OS packages and Compose configuration. See the [Microsoft Python driver guide](https://learn.microsoft.com/en-us/sql/connect/python/mssql-python/python-sql-driver-mssql-python-quickstart?view=sql-server-ver17) and [pyodbc connection documentation](https://github.com/mkleehammer/pyodbc/wiki/Connecting-to-SQL-Server-from-Windows).

## CI and demonstrations

The Actions workflow has a Python lint/unit-test job and a separate Compose build/SQL-test job. Each SQL job generates two disposable masked credentials, starts the database, runs `db-setup` twice, checks the restricted runtime login, starts the registry, seeds the department source, loads all three sources through the CLI, verifies an identical rerun, and runs integration tests. It saves test output and removes its disposable volume afterward. No real-data or LLM credentials are needed.

Actions is verification, not website hosting: its service containers last for the job. See [GitHub's service-container documentation](https://docs.github.com/en/actions/tutorials/use-containerized-services/use-docker-service-containers). A Codespaces launch path can be added later for remote live sessions. The primary portfolio deliverables remain the README, actual screenshots, and a recording described in the [demo guide](demo-guide.md).
