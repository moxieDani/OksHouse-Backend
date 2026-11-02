import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine

from app.db.database import database_engine_options, normalize_database_url
from app.db.migration import migrate_database


def main():
    parser = argparse.ArgumentParser(description="Copy Ok's House SQLite data to PostgreSQL.")
    parser.add_argument("sqlite_file", type=Path, help="Path to a consistent SQLite backup")
    args = parser.parse_args()

    target_url = os.environ.get("TARGET_DATABASE_URL", "")
    if not target_url.startswith("postgresql"):
        parser.error("TARGET_DATABASE_URL must be a PostgreSQL connection URL")
    if not args.sqlite_file.is_file():
        parser.error("SQLite backup file does not exist")

    source = create_engine(
        f"sqlite:///{args.sqlite_file.resolve()}",
        connect_args={"check_same_thread": False},
    )
    target_url = normalize_database_url(target_url)
    target = create_engine(target_url, **database_engine_options(target_url))
    try:
        print(json.dumps(migrate_database(source, target), ensure_ascii=False, sort_keys=True))
    finally:
        source.dispose()
        target.dispose()


if __name__ == "__main__":
    main()
