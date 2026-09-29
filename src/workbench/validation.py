"""Fixed v1 row rules. Validation never reads expected outputs or writes a database."""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

CONTRACT_DIR = Path("config/contracts/v1")
SOURCES = {
    "department-reference": "departments",
    "project-registry": "projects",
    "daily-activity": "activities",
}
VERSION = "1.0.0"
PRECEDENCE = [
    "ROW_REQUIRED",
    "ROW_FORMAT",
    "ROW_ENUM",
    "ROW_TIMESTAMP",
    "ACTIVITY_UNITS",
    "ACTIVITY_CONFLICT",
    "ACTIVITY_DUPLICATE",
    "PROJECT_UNKNOWN_DEPARTMENT",
    "ACTIVITY_UNKNOWN_PROJECT",
]


class LoadError(ValueError):
    """Safe fixed-code diagnostic for an entire load."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def contract(source: str) -> dict:
    return json.loads((CONTRACT_DIR / f"{SOURCES[source]}.json").read_text("utf-8"))


def parse_date(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Invalid date")
    return date.fromisoformat(value)


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
    ):
        raise ValueError("Invalid UTC timestamp")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Finding:
    rule: str
    field: str | None
    evidence: dict


@dataclass
class ValidatedRow:
    ordinal: int
    raw: dict
    values: dict = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    disposition: str = "accepted"
    primary_rule: str | None = None

    def add(self, rule: str, name: str | None = None, **evidence) -> None:
        if name is not None:
            evidence = {"value": self.raw.get(name), **evidence}
        self.findings.append(Finding(rule, name, evidence))


def validate_rows(
    source: str,
    records: list[dict],
    *,
    business_date: date | None = None,
    known_references: set[str] | None = None,
) -> list[ValidatedRow]:
    spec = contract(source)
    fields = spec["fields"]
    names = {f["name"] for f in fields}
    rows = []
    for ordinal, raw in enumerate(records, 1):
        if not isinstance(raw, dict) or set(raw) != names:
            raise LoadError("SRC_SCHEMA", "Source record fields do not match the v1 contract.")
        row = ValidatedRow(ordinal, raw)
        for definition in fields:
            name, kind = definition["name"], definition["type"]
            original = raw[name]
            value = original.strip() if isinstance(original, str) else original
            if value is None or value == "":
                row.add("ROW_REQUIRED", name)
                continue
            if kind == "string":
                if not isinstance(value, str):
                    row.add("ROW_FORMAT", name)
                    continue
                normalization = definition.get("normalization")
                if normalization == "trim_ascii_upper":
                    # Reject non-ASCII before uppercasing (e.g. sharp-s must not become SS).
                    if not value.isascii():
                        row.add("ROW_FORMAT", name)
                        continue
                    value = value.upper()
                    if not re.fullmatch(r"[A-Z0-9_-]+", value):
                        row.add("ROW_FORMAT", name)
                        continue
                elif normalization == "trim_lower":
                    value = value.lower()
                # NVARCHAR limits UTF-16 code units, not Python Unicode code points.
                if len(value.encode("utf-16-le")) // 2 > definition.get("max_length", 100):
                    row.add("ROW_FORMAT", name)
                    continue
                if "allowed" in definition and value not in definition["allowed"]:
                    row.add("ROW_ENUM", name)
                    continue
            elif kind == "boolean":
                if type(value) is not bool:
                    row.add("ROW_FORMAT", name)
                    continue
            elif kind == "date":
                try:
                    value = parse_date(value)
                except (ValueError, TypeError):
                    row.add("ROW_FORMAT", name)
                    continue
                if business_date is not None and value != business_date:
                    raise LoadError("SRC_BUSINESS_DATE", "Row dates must match the manifest date.")
            elif kind == "utc_timestamp":
                try:
                    value = parse_timestamp(value)
                except (ValueError, TypeError):
                    row.add("ROW_TIMESTAMP", name)
                    continue
            elif kind == "integer":
                if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
                    row.add("ACTIVITY_UNITS", name)
                    continue
                digits = value.lstrip("0") or "0"
                if len(digits) > 10:
                    row.add("ACTIVITY_UNITS", name)
                    continue
                value = int(digits)
                if value > 2147483647:
                    row.add("ACTIVITY_UNITS", name)
                    continue
            row.values[name] = value
        if source == "daily-activity":
            status, units = row.values.get("activity_status"), row.values.get("completed_units")
            if units is not None and (
                (status == "completed" and units == 0)
                or (status in {"planned", "cancelled"} and units != 0)
            ):
                row.add("ACTIVITY_UNITS", "completed_units", activity_status=status)
        reference_field = {"project-registry": "department_id", "daily-activity": "project_id"}.get(
            source
        )
        if reference_field and reference_field in row.values:
            value = row.values[reference_field]
            if known_references is None:
                raise LoadError("DEPENDENCY_UNAVAILABLE", "Load the required reference first.")
            if value not in known_references:
                rule = (
                    "PROJECT_UNKNOWN_DEPARTMENT"
                    if source == "project-registry"
                    else "ACTIVITY_UNKNOWN_PROJECT"
                )
                row.add(rule, reference_field, normalized_value=value, reference_found=False)
        rows.append(row)

    groups = defaultdict(list)
    for row in rows:
        if all(key in row.values for key in spec["key"]):
            groups[tuple(row.values[key] for key in spec["key"])].append(row)
    for group in groups.values():
        if len(group) < 2:
            continue
        if source != "daily-activity":
            raise LoadError("REF_DUPLICATE", "Reference keys must be unique after normalization.")

        # Invalid fields retain their trimmed raw value for conflict comparison.
        def payload(row):
            values = []
            for definition in fields:
                value = row.values.get(definition["name"], row.raw[definition["name"]])
                if isinstance(value, str):
                    value = value.strip()
                    if definition.get("normalization") == "trim_lower":
                        value = value.lower()
                    elif definition.get("normalization") == "trim_ascii_upper" and value.isascii():
                        value = value.upper()
                values.append(value)
            return tuple(values)

        if any(payload(row) != payload(group[0]) for row in group[1:]):
            for row in group:
                row.add("ACTIVITY_CONFLICT", group_ordinals=[item.ordinal for item in group])
        else:
            for row in group[1:]:
                row.add("ACTIVITY_DUPLICATE", duplicate_of_ordinal=group[0].ordinal)
    for row in rows:
        if row.findings:
            row.primary_rule = min((f.rule for f in row.findings), key=PRECEDENCE.index)
            row.disposition = (
                "excluded_duplicate"
                if row.primary_rule == "ACTIVITY_DUPLICATE"
                else "excluded_invalid"
            )
    return rows
