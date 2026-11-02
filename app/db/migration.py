import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Integer, func, select, text
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db.database import Base


def _canonical_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"bytes": bytes(value).hex()}
    return value


def _table_rows(connection, table):
    statement = select(table)
    primary_key = list(table.primary_key.columns)
    if primary_key:
        statement = statement.order_by(*primary_key)
    return [dict(row) for row in connection.execute(statement).mappings()]


def _digest(rows):
    digest = hashlib.sha256()
    for row in rows:
        encoded = json.dumps(
            {key: _canonical_value(value) for key, value in row.items()},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")
    return digest.hexdigest()


def migrate_database(source_engine: Engine, target_engine: Engine) -> dict:
    """Copy the app's SQLAlchemy tables without overwriting target data."""
    if source_engine.dialect.name != "sqlite":
        raise ValueError("source database must be SQLite")
    if target_engine.dialect.name not in {"sqlite", "postgresql"}:
        raise ValueError("target database must be PostgreSQL")

    Base.metadata.create_all(target_engine)
    table_rows = {}
    results = {}

    with source_engine.connect() as source, target_engine.begin() as target:
        source_tables = set(inspect(source).get_table_names())
        for table in Base.metadata.sorted_tables:
            existing_count = target.scalar(select(func.count()).select_from(table))
            if existing_count:
                raise ValueError(f"target table {table.name} is not empty")

        for table in Base.metadata.sorted_tables:
            rows = _table_rows(source, table) if table.name in source_tables else []
            if rows:
                target.execute(table.insert(), rows)
            table_rows[table.name] = rows

            if target_engine.dialect.name == "postgresql":
                for column in table.primary_key.columns:
                    if not isinstance(column.type, Integer):
                        continue
                    maximum = target.scalar(select(func.max(column)))
                    if maximum is not None:
                        target.execute(
                            text(
                                "SELECT setval(pg_get_serial_sequence(:table_name, :column_name), "
                                ":maximum, true)"
                            ),
                            {
                                "table_name": table.name,
                                "column_name": column.name,
                                "maximum": maximum,
                            },
                        )

        for table in Base.metadata.sorted_tables:
            expected = _digest(table_rows[table.name])
            actual = _digest(_table_rows(target, table))
            if actual != expected:
                raise RuntimeError(f"data verification failed for table {table.name}")
            results[table.name] = {"rows": len(table_rows[table.name]), "sha256": actual}

    return results
