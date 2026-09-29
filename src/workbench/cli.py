"""Small operational CLI. Output never contains connection strings or driver errors."""

import argparse
import json
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from workbench import bootstrap, db, demo, freshness, migrations, pipeline, reports
from workbench.config import ConfigurationError, load_settings
from workbench.validation import LoadError, parse_date, parse_timestamp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workbench")
    parser.add_argument("--env-file", type=Path, help="Explicit configuration file (optional)")
    parser.add_argument("--migration-dir", type=Path, default=migrations.DEFAULT_MIGRATIONS)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--registry-url", default="http://mock-registry:8001/projects")
    parser.add_argument("--reference-hash")
    parser.add_argument("--actor", default="cli")
    parser.add_argument("--business-date", type=parse_date)
    parser.add_argument("--load-id")
    parser.add_argument("--output-dir", type=Path, default=Path("runs/demo"))
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument(
        "--output", type=Path, help="New evidence JSON file; existing files are preserved"
    )
    parser.add_argument(
        "--now", type=parse_timestamp, help="Injected UTC clock: YYYY-MM-DDTHH:MM:SSZ"
    )
    parser.add_argument(
        "command",
        choices=(
            "config-check",
            "health",
            "db-smoke",
            "db-create",
            "migrate",
            "db-setup",
            "seed-departments",
            "load-departments",
            "load-projects",
            "load-activities",
            "freshness",
            "reconcile",
            "evidence",
            "demo",
        ),
    )
    args = parser.parse_args(argv)
    if args.command == "load-activities" and (args.csv is None or args.manifest is None):
        parser.error("load-activities requires --csv and --manifest")
    if args.command == "load-departments" and not args.reference_hash:
        parser.error("load-departments requires --reference-hash")
    if args.command == "freshness" and args.business_date is None:
        parser.error("freshness requires --business-date")
    if args.command in {"reconcile", "evidence"} and (
        (args.load_id is None) == (args.business_date is None)
    ):
        parser.error("reconcile/evidence requires exactly one of --load-id or --business-date")
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
            elif args.command == "db-setup":
                result = bootstrap.setup_database(settings, args.migration_dir)
            elif args.command == "seed-departments":
                migrations.validate_database_name(settings.database)
                sql = Path("fixtures/generated/reference/departments.sql").read_text("utf-8")
                with (
                    closing(db.connect(settings)) as connection,
                    closing(connection.cursor()) as cursor,
                ):
                    migrations.execute_batch(cursor, sql)
                    connection.commit()
                result = {"status": "ok", "check": "department-seed"}
            elif args.command == "load-departments":
                result = pipeline.load_departments(settings, args.reference_hash, actor=args.actor)
            elif args.command == "load-projects":
                result = pipeline.load_projects(settings, args.registry_url, actor=args.actor)
            elif args.command == "demo":
                result = demo.run(settings, args.output_dir, args.registry_url)
            elif args.command == "freshness":
                now = args.now.replace(tzinfo=UTC) if args.now else datetime.now(UTC)
                result = freshness.inspect(settings, args.business_date, now)
            elif args.command in {"reconcile", "evidence"}:
                result = reports.read(
                    settings, load_id=args.load_id, business_date=args.business_date
                )
                if args.command == "evidence":
                    result = result["packet"]
                    if args.output:
                        with args.output.open("x", encoding="utf-8") as stream:
                            json.dump(result, stream, indent=2, ensure_ascii=False)
                            stream.write("\n")
                        result = {
                            "status": "ok",
                            "check": "evidence-export",
                            "load_id": result["load_id"],
                        }
                elif args.format == "text":
                    print(reports.render(result))
                    return 0
            else:
                result = pipeline.load_activities(
                    settings, args.csv, args.manifest, actor=args.actor
                )
        except (migrations.MigrationError, bootstrap.BootstrapError, LoadError) as error:
            print(json.dumps({"status": "error", "message": str(error)}), file=sys.stderr)
            return 4
        except OSError:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": "File operation failed. "
                        "Use an available output directory and a new filename.",
                    }
                ),
                file=sys.stderr,
            )
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
    return 5 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
