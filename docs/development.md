# Foundation development setup

## P01 acceptance status

Implemented: Python 3.12 package, CLI entry point, configuration validation, redacted CLI errors, uv lockfile, unit tests, opt-in SQL integration tests, Docker runtime/test targets, Compose database readiness, and a GitHub Actions workflow.

Verified on Windows: Python 3.12.14, uv 0.12.20, mssql-python 1.15.0 import, lint/format checks, and 13 passing unit tests. Two live SQL integration tests are skipped by default. This is not evidence that SQL connectivity or transactions passed.

P01 remains open until a Docker host builds both images, starts SQL Server, passes `health` and `db-smoke`, and passes the integration suite with `--run-sql`. The workflow is prepared locally; it has not been pushed or executed on GitHub. Docker Desktop and native SQL Server have not been installed as part of this work.

## Container setup

Use an x86-64 Docker host with Linux containers, Compose v2 or later, and sufficient memory for SQL Server plus the Python container; allocate at least 4 GB for this development stack. Microsoft's SQL Server container support is Linux x86-64; ARM emulation is not a verified setup for this repository. See [Microsoft's container guide](https://learn.microsoft.com/en-us/sql/linux/install-upgrade/quickstart-install-docker?view=sql-server-ver17).

Follow the Compose commands in the [README](../README.md). The SQL image is pinned to the official `2022-latest` digest resolved on 2026-09-28. Refresh the digest deliberately and rerun SQL tests when updating it. SQL readiness uses a real query with `sqlcmd`; dependent services wait for the database to become healthy, as described in [Docker's startup-order guidance](https://docs.docker.com/compose/how-tos/startup-order/).

Configuration:

| Setting | Meaning |
|---|---|
| `WB_SQL_PASSWORD` | Generated local demo password; required by Compose; never commit it |
| `WB_SQL_SERVER` | Host/port for direct Python use; Compose explicitly sets `sqlserver,1433` |
| `WB_SQL_DATABASE` | Existing target database; Compose uses `master` for the P01 temporary-table probe |
| `WB_SQL_USERNAME` | SQL login; P01 Compose uses `sa` for bootstrap checks |
| `WB_SQL_DRIVER` | `mssql-python`, or explicitly selected `pyodbc` fallback |
| `WB_SQL_TRUST_CERTIFICATE` | `true` for this self-signed development container; encryption remains enabled |
| `WB_SQL_CONNECT_TIMEOUT` | Connection/query timeout in seconds, from 1 to 30 |

The Compose environment intentionally overrides non-password connection settings to target its own database. P03 will introduce the application database and restricted runtime credentials; the eventual web application must not use the P01 bootstrap login.

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

Commands return JSON and exit with 0 for success, 2 for invalid configuration, and 3 for unavailable drivers or failed SQL checks. No environment file is loaded implicitly. `--env-file` explicitly opts into a file; process variables override its values. The existing root `.env` is left untouched.

## Live SQL checks and driver fallback

`health` executes a read-only round trip. `db-smoke` binds text containing Unicode, quotes, and punctuation; commits one row to a session-local temporary table; rolls back a second row; and verifies that only the committed row remains. The temporary table disappears when the connection closes. No application data is modified.

The Compose test service passes `--run-sql`, so missing or failing SQL access fails the tests instead of silently skipping them. The default local pytest invocation clearly reports SQL tests as skipped.

If `mssql-python` blocks progress, install the optional Python fallback with `uv sync --locked --extra odbc`, install Microsoft ODBC Driver 18 on the execution host, and explicitly set `WB_SQL_DRIVER=pyodbc` for direct Python checks. Repeat the same live smoke tests before choosing the fallback. The default Docker image currently contains the primary driver only; adopting the fallback there also requires updating its OS packages and Compose configuration. See the [Microsoft Python driver guide](https://learn.microsoft.com/en-us/sql/connect/python/mssql-python/python-sql-driver-mssql-python-quickstart?view=sql-server-ver17) and [pyodbc connection documentation](https://github.com/mkleehammer/pyodbc/wiki/Connecting-to-SQL-Server-from-Windows).

## CI and demonstrations

The Actions workflow has a Python lint/unit-test job and a separate Compose build/SQL-test job. Each SQL job generates a disposable masked credential, starts the database, checks the runtime image, runs integration tests, saves test output, and removes its database volume afterward. No real-data or LLM credentials are needed.

Actions is verification, not website hosting: its service containers last for the job. See [GitHub's service-container documentation](https://docs.github.com/en/actions/tutorials/use-containerized-services/use-docker-service-containers). A Codespaces launch path can be added later for remote live sessions. The primary portfolio deliverables remain the README, actual screenshots, and a recording described in the [demo guide](demo-guide.md).
