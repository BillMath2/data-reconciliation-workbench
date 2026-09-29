"""Deterministic synthetic source data. Never reads or generates expected outcomes."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

VERSION = "1.0.0"
BUSINESS_DATE = "2026-09-25"
HEADERS = (
    "activity_id",
    "project_id",
    "activity_date",
    "activity_status",
    "completed_units",
    "source_updated_at",
)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def reference_hash(departments: list[dict], projects: list[dict]) -> str:
    canonical = json.dumps(
        {
            "departments": sorted(departments, key=lambda row: row["department_id"]),
            "projects": sorted(projects, key=lambda row: row["project_id"]),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _csv_bytes(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _department_sql(departments: list[dict]) -> bytes:
    values = ",\n".join(
        f"    (N'{row['department_id']}', N'{row['department_name']}', {int(row['is_active'])})"
        for row in departments
    )
    # Only generated, fixed synthetic strings enter this template.
    return f"""-- Synthetic source bootstrap only; operational migrations belong to P03.
-- Execute in a disposable user database. No GO separators; one DB-API batch.
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF DB_NAME() IN ('master', 'model', 'msdb', 'tempdb')
    THROW 51000, 'Use a disposable user database for source fixtures.', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    IF SCHEMA_ID(N'source') IS NULL EXEC(N'CREATE SCHEMA source');
    IF OBJECT_ID(N'source.Department', N'U') IS NULL
        CREATE TABLE source.Department (
            department_id NVARCHAR(16) NOT NULL PRIMARY KEY,
            department_name NVARCHAR(100) NOT NULL,
            is_active BIT NOT NULL
        );
    DECLARE @seed TABLE (
        department_id NVARCHAR(16), department_name NVARCHAR(100), is_active BIT
    );
    INSERT INTO @seed VALUES
{values};
    IF EXISTS (
        SELECT department_id, department_name, is_active FROM source.Department
        EXCEPT SELECT department_id, department_name, is_active FROM @seed
    ) THROW 51001, 'Reference data differs; use a fresh demo database.', 1;
    INSERT INTO source.Department (department_id, department_name, is_active)
    SELECT s.department_id, s.department_name, s.is_active FROM @seed AS s
    WHERE NOT EXISTS (
        SELECT 1 FROM source.Department AS d WHERE d.department_id = s.department_id
    );
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
""".encode()


def build_fixtures() -> dict[str, bytes]:
    """Return source artifacts only, with fixed dates/order and no random inputs."""
    departments = [
        {
            "department_id": f"DEPT-{i:02}",
            "department_name": f"Synthetic Department {i}",
            "is_active": True,
        }
        for i in range(1, 6)
    ]
    projects = [
        {
            "project_id": f"PRJ-{i:03}",
            "project_name": f"Synthetic Research Project {i:02}",
            "department_id": f"DEPT-{(i - 1) % 5 + 1:02}",
            "project_status": "active",
            "updated_at": "2026-09-24T12:00:00Z",
        }
        for i in range(1, 26)
    ]
    bad_projects = [dict(row) for row in projects]
    bad_projects[0]["department_id"] = "DEPT-UNKNOWN"
    refs = {
        "default": reference_hash(departments, projects),
        "unknown-department": reference_hash(departments, bad_projects),
    }
    artifacts = {
        "reference/departments.json": json_bytes(departments),
        "reference/departments.sql": _department_sql(departments),
    }
    for name, records in (("default", projects), ("unknown-department", bad_projects)):
        artifacts[f"reference/projects-{name}.json"] = json_bytes(
            {
                "schema_version": VERSION,
                "snapshot_id": f"registry-{name}-v1",
                "reference_set_sha256": refs[name],
                "exported_at": "2026-09-24T12:00:00Z",
                "total_count": 25,
                "items": records,
            }
        )
    clean = [
        {
            "activity_id": f"ACT-{i:04}",
            "project_id": f"PRJ-{(i - 1) % 25 + 1:03}",
            "activity_date": BUSINESS_DATE,
            "activity_status": "completed",
            "completed_units": "3" if i == 1 else "2",
            "source_updated_at": "2026-09-25T23:00:00Z",
        }
        for i in range(1, 101)
    ]
    duplicates = [dict(row) for row in clean[:98]] + [dict(clean[0]), dict(clean[1])]
    golden = [dict(row) for row in duplicates]
    for ordinal in (95, 96, 97):
        golden[ordinal - 1]["project_id"] = "PRJ-UNKNOWN"
    golden[97]["project_id"] = ""
    corrected = [dict(row) for row in clean[:98]]
    for row in corrected[94:]:
        row["source_updated_at"] = "2026-09-26T10:00:00Z"
    conflict = [dict(row) for row in clean]
    conflict[1].update(activity_id="ACT-0001", project_id="PRJ-001")
    invalid_status = [dict(row) for row in clean]
    invalid_status[0]["activity_status"] = "unrecognized"
    invalid_units = [dict(row) for row in clean]
    invalid_units[0]["completed_units"] = "not-a-number"
    mixed_date = [dict(row) for row in clean]
    mixed_date[0]["activity_date"] = "2026-09-24"
    datasets = {
        "clean": clean,
        "golden": golden,
        "corrected": corrected,
        "duplicates": duplicates,
        "conflict": conflict,
        "invalid-status": invalid_status,
        "invalid-units": invalid_units,
        "unknown-department": clean,
        "mixed-date": mixed_date,
        "manifest-mismatch": clean,
        "schema-mismatch": clean,
        "empty": [],
    }
    for name, rows in datasets.items():
        reference = "unknown-department" if name == "unknown-department" else "default"
        data = _csv_bytes(rows)
        if name == "schema-mismatch":
            data = data.replace(b"completed_units", b"unrecognized_column", 1)
        artifacts[f"activity/{name}.csv"] = data
        artifacts[f"activity/{name}.manifest.json"] = json_bytes(
            {
                "schema_version": VERSION,
                "source_id": "daily-activity",
                "business_date": BUSINESS_DATE,
                "exported_at": "2026-09-26T10:00:00Z"
                if name == "corrected"
                else "2026-09-26T09:00:00Z",
                "row_count": 99 if name == "manifest-mismatch" else len(rows),
                "reference_set_id": f"reference-{reference}-v1",
                "reference_set_sha256": refs[reference],
            }
        )
    artifacts["index.json"] = json_bytes(
        {
            "fixture_version": VERSION,
            "reference_sets": refs,
            "sha256": {
                name: hashlib.sha256(data).hexdigest() for name, data in sorted(artifacts.items())
            },
        }
    )
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--output", type=Path, help="Write generated source files into this directory"
    )
    mode.add_argument(
        "--check", type=Path, help="Check a directory against generated bytes; no writes"
    )
    args = parser.parse_args(argv)
    artifacts = build_fixtures()
    if args.check:
        actual = {
            p.relative_to(args.check).as_posix(): p.read_bytes()
            for p in args.check.rglob("*")
            if p.is_file()
        }
        mismatches = sorted(
            name
            for name in actual.keys() | artifacts.keys()
            if actual.get(name) != artifacts.get(name)
        )
        print(
            json.dumps(
                {
                    "status": "error" if mismatches else "ok",
                    "files": len(artifacts),
                    "mismatches": mismatches,
                }
            )
        )
        return int(bool(mismatches))
    for name, data in artifacts.items():
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(json.dumps({"status": "ok", "files": len(artifacts)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
