"""Bounded CSV, REST, and SQL adapters retaining captured input on validation failures."""

import base64
import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date
from http.client import HTTPException
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen

from workbench.validation import VERSION, LoadError, contract, parse_date, parse_timestamp

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000


def canonical(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json(content: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("Nonfinite JSON value")

    return json.loads(
        content.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant
    )


@dataclass
class Capture:
    source: str
    content: bytes = b""
    metadata: dict = field(default_factory=dict)
    records: list[dict] = field(default_factory=list)
    reference_hash: str | None = None
    business_date: date | None = None
    error: LoadError | None = None


def bounded_read(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise LoadError("SRC_SCHEMA", "Source exceeds the demo's 10 MiB capture limit.")
    return data


def validate_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise LoadError("SRC_SCHEMA", "Invalid reference-set hash.")
    return value


def activity_capture(csv_path: Path, manifest_path: Path) -> Capture:
    result = Capture("daily-activity")
    try:
        result.content = bounded_read(csv_path)
        manifest_bytes = bounded_read(manifest_path)
        # Preserve original metadata bytes even when parsing or verification fails.
        result.metadata["manifest_base64"] = base64.b64encode(manifest_bytes).decode("ascii")
        manifest = strict_json(manifest_bytes)
        spec = contract(result.source)
        if not isinstance(manifest, dict) or set(manifest) != set(spec["manifest_required"]):
            raise LoadError("SRC_SCHEMA", "Manifest fields do not match the v1 contract.")
        if manifest["schema_version"] != VERSION or manifest["source_id"] != result.source:
            raise LoadError("SRC_SCHEMA", "Unsupported manifest version or source.")
        result.business_date = parse_date(manifest["business_date"])
        parse_timestamp(manifest["exported_at"])
        if type(manifest["row_count"]) is not int or not 0 <= manifest["row_count"] <= MAX_ROWS:
            raise LoadError("SRC_SCHEMA", "Invalid manifest row count.")
        if (
            not isinstance(manifest["reference_set_id"], str)
            or not manifest["reference_set_id"].strip()
        ):
            raise LoadError("SRC_SCHEMA", "Manifest requires a reference-set identifier.")
        result.reference_hash = validate_hash(manifest["reference_set_sha256"])
        result.metadata["manifest"] = manifest
        stream = io.StringIO(result.content.decode("utf-8"), newline="")
        reader = csv.reader(stream, strict=True)
        headers = next(reader, None)
        if headers != spec["transport"]["header_order"]:
            raise LoadError("SRC_SCHEMA", "CSV header does not match the v1 contract.")
        for cells in reader:
            if len(cells) != len(headers) or len(result.records) >= MAX_ROWS:
                raise LoadError("SRC_SCHEMA", "Malformed CSV record or row limit exceeded.")
            result.records.append(dict(zip(headers, cells, strict=True)))
        if len(result.records) != manifest["row_count"]:
            raise LoadError("SRC_MANIFEST_COUNT", "CSV row count differs from its manifest.")
    except LoadError as error:
        result.error = error
    except OSError:
        result.error = LoadError("SOURCE_UNAVAILABLE", "CSV or manifest could not be read.")
    except (ValueError, TypeError, csv.Error, UnicodeError):
        result.error = LoadError("SRC_SCHEMA", "Invalid CSV encoding or manifest metadata.")
    return result


def fetch_page(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise LoadError("SRC_PAGINATION", "API response exceeds the capture limit.")
    return data


def registry_capture(url: str, fetch=fetch_page) -> Capture:
    result = Capture("project-registry")
    pages = []
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username:
            raise LoadError(
                "SRC_SCHEMA", "Registry must be an HTTP(S) endpoint without credentials."
            )
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if "cursor" in query:
            raise LoadError("SRC_PAGINATION", "Start registry capture at the first page.")
        cursor, seen, envelope = None, set(), None
        required = set(contract(result.source)["envelope"]["required"])
        for _ in range(100):
            params = {**query, **({"cursor": cursor} if cursor is not None else {})}
            page_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))
            content = fetch(page_url)
            if sum(len(p) for p in pages) + len(content) > MAX_BYTES:
                raise LoadError("SRC_PAGINATION", "Registry capture exceeds the demo size limit.")
            pages.append(content)
            page = strict_json(content)
            if (
                not isinstance(page, dict)
                or set(page) != required
                or not isinstance(page["items"], list)
            ):
                raise LoadError("SRC_SCHEMA", "Registry envelope does not match the v1 contract.")
            metadata = {k: v for k, v in page.items() if k not in {"items", "next_cursor"}}
            if metadata["schema_version"] != VERSION:
                raise LoadError("SRC_SCHEMA", "Unsupported registry schema version.")
            parse_timestamp(metadata["exported_at"])
            validate_hash(metadata["reference_set_sha256"])
            if (
                not isinstance(metadata["snapshot_id"], str)
                or not metadata["snapshot_id"]
                or type(metadata["total_count"]) is not int
                or not 0 <= metadata["total_count"] <= MAX_ROWS
            ):
                raise LoadError("SRC_SCHEMA", "Invalid registry snapshot metadata.")
            if envelope is not None and metadata != envelope:
                raise LoadError(
                    "SRC_PAGINATION", "Registry snapshot metadata changed between pages."
                )
            envelope = metadata
            result.metadata = envelope
            result.reference_hash = metadata["reference_set_sha256"]
            result.records.extend(page["items"])
            if len(result.records) > metadata["total_count"]:
                raise LoadError("SRC_PAGINATION", "Registry returned more rows than declared.")
            cursor = page["next_cursor"]
            if cursor is None:
                if len(result.records) != metadata["total_count"]:
                    raise LoadError("SRC_PAGINATION", "Registry pagination is incomplete.")
                break
            if not isinstance(cursor, str) or not cursor or cursor in seen or not page["items"]:
                raise LoadError("SRC_PAGINATION", "Registry cursor is invalid or repeated.")
            seen.add(cursor)
        else:
            raise LoadError("SRC_PAGINATION", "Registry exceeded the page limit.")
    except LoadError as error:
        result.error = error
    except (ValueError, TypeError, UnicodeError):
        result.error = LoadError("SRC_SCHEMA", "Registry returned invalid JSON or metadata.")
    except (OSError, HTTPException):
        result.error = LoadError("SOURCE_UNAVAILABLE", "Registry request failed or timed out.")
    finally:
        result.content = canonical(
            {"pages_base64": [base64.b64encode(p).decode("ascii") for p in pages]}
        )
    return result


def department_capture(cursor, reference_hash: str) -> Capture:
    result = Capture("department-reference", reference_hash=reference_hash)
    validate_hash(reference_hash)
    cursor.execute(
        "SELECT TOP (10001) department_id, department_name, is_active "
        "FROM source.Department ORDER BY department_id"
    )
    result.records = [
        dict(
            zip(
                ("department_id", "department_name", "is_active"),
                (r[0], r[1], bool(r[2])),
                strict=True,
            )
        )
        for r in cursor.fetchall()
    ]
    result.content = canonical(result.records)
    result.metadata = {"reference_set_sha256": reference_hash}
    if len(result.records) > MAX_ROWS:
        result.error = LoadError("SRC_SCHEMA", "Department source exceeds the row limit.")
    return result
