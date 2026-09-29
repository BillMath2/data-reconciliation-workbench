"""Record a real SQL walkthrough in a fresh, migrated and source-seeded demo database."""

import json
import os
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from workbench import pipeline, reports
from workbench.db import connect
from workbench.validation import LoadError


def run(settings, directory: Path, registry_url: str) -> dict:
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute("SELECT COUNT(*) FROM ops.Load WHERE source_id='daily-activity'")
        if cursor.fetchone()[0]:
            raise LoadError(
                "DEMO_NEEDS_FRESH_DATABASE",
                "Use a fresh migrated demo database; "
                "the walkthrough never deletes previous load history.",
            )
        cursor.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') AS VARCHAR(32))")
        sql_version = cursor.fetchone()[0]
    directory.mkdir(parents=True, exist_ok=False)
    expected = json.loads(Path("fixtures/expected/golden.json").read_text("utf-8"))
    fixtures = Path("fixtures/generated")
    refs = json.loads((fixtures / "index.json").read_text("utf-8"))["reference_sets"]
    started = time.monotonic()
    events, frames = [], []

    def record(title, text):
        output = title + "\n" + text + "\n"
        print(output, flush=True)
        events.append([round(time.monotonic() - started, 3), "o", output.replace("\n", "\r\n")])
        frames.append({"title": title, "text": text})

    def success(result):
        if result["status"] not in {"published", "published_with_exceptions", "no_op"}:
            raise LoadError("DEMO_FAILED", "A demo load failed; inspect its saved attempt.")
        return result

    success(pipeline.load_departments(settings, refs["default"], actor="demo"))
    success(pipeline.load_projects(settings, registry_url, actor="demo"))
    reports_by_name = {}
    for name in ("golden", "corrected", "repeat"):
        fixture = "corrected" if name == "repeat" else name
        result = success(
            pipeline.load_activities(
                settings,
                fixtures / f"activity/{fixture}.csv",
                fixtures / f"activity/{fixture}.manifest.json",
                actor="demo",
            )
        )
        if name == "repeat" and result["status"] != "no_op":
            raise LoadError("DEMO_FAILED", "Identical rerun did not return no_op.")
        report = reports.read(settings, load_id=result["load_id"])
        wanted = expected[fixture]
        for key in (
            "raw_rows",
            "accepted_rows",
            "source_completed_count",
            "curated_completed_count",
            "source_completed_units",
            "curated_completed_units",
        ):
            if report["summary"][key] != wanted[key]:
                raise LoadError(
                    "DEMO_FAILED", "Observed SQL result differs from independent expectations."
                )
        reports_by_name[name] = report
        (directory / f"{name}.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        (directory / f"{name}-evidence.json").write_text(
            json.dumps(report["packet"], indent=2) + "\n", encoding="utf-8"
        )
        record(f"workbench demo | stage: {name}", reports.render(report))
    historical = reports.read(settings, load_id=reports_by_name["golden"]["publication_load_id"])
    if historical["packet"] != reports_by_name["golden"]["packet"] or historical["is_current"]:
        raise LoadError(
            "DEMO_FAILED", "Historical evidence changed or publication was not superseded."
        )
    manifest = {
        "schema_version": 1,
        "mode": "sql-server",
        "status": "verified",
        "recorded_at": datetime.now(UTC).isoformat(),
        "sql_server_version": sql_version,
        "source_commit": os.environ.get("WB_BUILD_REVISION"),
        "frames": frames,
        "checks": [
            "golden expectations",
            "corrected expectations",
            "no-op rerun",
            "immutable historical evidence",
        ],
    }
    (directory / "recording.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    header = {
        "version": 2,
        "width": 110,
        "height": 30,
        "title": "Data Reconciliation Workbench: SQL demo",
    }
    (directory / "demo.cast").write_text(
        "\n".join(json.dumps(item) for item in [header, *events]) + "\n", encoding="utf-8"
    )
    (directory / "transcript.txt").write_text(
        "\n\n".join(f["title"] + "\n" + f["text"] for f in frames) + "\n", encoding="utf-8"
    )
    return {"status": "ok", "check": "sql-demo", "stages": 3}
