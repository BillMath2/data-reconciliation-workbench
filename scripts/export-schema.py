"""Export a credential-free SQL catalog for the release dictionary (read-only)."""

import argparse
import json
from contextlib import closing
from pathlib import Path

from workbench.config import load_settings
from workbench.db import connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with closing(connect(load_settings())) as connection, closing(connection.cursor()) as cursor:

        def rows(sql, names):
            cursor.execute(sql)
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

        columns = rows(
            "SELECT s.name, o.name, RTRIM(o.type), c.name, t.name, c.max_length, "
            "c.precision, c.scale, "
            "c.is_nullable, c.is_identity FROM sys.columns c JOIN sys.objects o ON "
            "o.object_id=c.object_id "
            "JOIN sys.schemas s ON s.schema_id=o.schema_id JOIN sys.types t ON "
            "t.user_type_id=c.user_type_id "
            "WHERE o.type IN ('U','V') AND s.name IN "
            "('meta','source','ops','stg','core','report') "
            "ORDER BY s.name,o.name,c.column_id",
            (
                "schema",
                "object",
                "kind",
                "column",
                "type",
                "max_length_bytes",
                "precision",
                "scale",
                "nullable",
                "identity",
            ),
        )
        foreign_keys = rows(
            "SELECT fk.name, "
            "OBJECT_SCHEMA_NAME(fk.parent_object_id),OBJECT_NAME(fk.parent_object_id), "
            "COL_NAME(fkc.parent_object_id,fkc.parent_column_id), "
            "OBJECT_SCHEMA_NAME(fk.referenced_object_id), "
            "OBJECT_NAME(fk.referenced_object_id), "
            "COL_NAME(fkc.referenced_object_id,fkc.referenced_column_id) "
            "FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON "
            "fkc.constraint_object_id=fk.object_id "
            "ORDER BY fk.name,fkc.constraint_column_id",
            ("name", "schema", "table", "column", "target_schema", "target_table", "target_column"),
        )
        indexes = rows(
            "SELECT "
            "OBJECT_SCHEMA_NAME(i.object_id),OBJECT_NAME(i.object_id),i.name,i.is_primary_key, "
            "i.is_unique,i.filter_definition,c.name,ic.key_ordinal,ic.is_included_column "
            "FROM sys.indexes i JOIN sys.index_columns ic ON i.object_id=ic.object_id AND "
            "i.index_id=ic.index_id "
            "JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id "
            "WHERE OBJECT_SCHEMA_NAME(i.object_id) IN ('meta','source','ops','stg','core') "
            "ORDER BY i.object_id,i.index_id,ic.index_column_id",
            (
                "schema",
                "table",
                "index",
                "primary",
                "unique",
                "filter",
                "column",
                "key_ordinal",
                "included",
            ),
        )
        versions = rows(
            "SELECT version,name FROM meta.SchemaMigration ORDER BY version", ("version", "name")
        )
        assert len({(c["schema"], c["object"]) for c in columns if c["kind"] == "U"}) == 12
        assert len({(c["schema"], c["object"]) for c in columns if c["kind"] == "V"}) == 3
        connection.rollback()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "migrations": versions,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print("Read-only schema export: twelve tables and three views.")


if __name__ == "__main__":
    main()
