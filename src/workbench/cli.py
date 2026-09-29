"""Small operational CLI. Output never contains connection strings or driver errors."""

import argparse
import json
import sys
from pathlib import Path

from workbench import bootstrap, db, migrations
from workbench.config import ConfigurationError, load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workbench")
    parser.add_argument("--env-file", type=Path, help="Explicit configuration file (optional)")
    parser.add_argument("--migration-dir", type=Path, default=migrations.DEFAULT_MIGRATIONS)
    parser.add_argument(
        "command",
        choices=("config-check", "health", "db-smoke", "db-create", "migrate", "db-setup"),
    )
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.env_file)
    except ConfigurationError as error:
        print(json.dumps({"status": "error", "message": str(error)}), file=sys.stderr)
        return 2

    if args.command == "config-check":
        result = {"status": "ok", "check": "configuration", "driver": settings.driver}
    else:
        try:
            if args.command == "health":
                result = db.health(settings)
            elif args.command == "db-smoke":
                result = db.smoke(settings)
            elif args.command == "db-create":
                result = bootstrap.create_database(settings)
            elif args.command == "migrate":
                result = migrations.migrate(settings, args.migration_dir)
            else:
                result = bootstrap.setup_database(settings, args.migration_dir)
        except (migrations.MigrationError, bootstrap.BootstrapError) as error:
            print(json.dumps({"status": "error", "message": str(error)}), file=sys.stderr)
            return 4
        except ImportError:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": "Database driver unavailable. Sync dependencies; for pyodbc, "
                        "install the odbc extra and Microsoft ODBC Driver 18.",
                    }
                ),
                file=sys.stderr,
            )
            return 3
        except Exception:
            # Driver messages can include server, login, and connection-string values.
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": "SQL check failed. Verify database readiness, credentials, "
                        "TLS settings, and driver compatibility. Driver details are withheld.",
                    }
                ),
                file=sys.stderr,
            )
            return 3
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
