from __future__ import annotations

from pathlib import Path

from autumn_ledger.database import Database
from autumn_ledger.models import ApplicationRecord
from autumn_ledger.repository import ApplicationRepository


def table_names(database: Database) -> set[str]:
    rows = database.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def test_first_initialization_creates_database_and_tables(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "ledger.db"
    database = Database(path)
    database.initialize()
    assert path.exists()
    assert {"applications", "status_history"} <= table_names(database)
    assert database.foreign_keys_enabled()
    database.close()


def test_repeated_initialization_keeps_existing_data(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    first = Database(path)
    first.initialize()
    record_id = ApplicationRepository(first).create_application(
        ApplicationRecord("甲公司", "算法工程师", "2026-07-26", "已投递")
    )
    first.close()

    second = Database(path)
    second.initialize()
    loaded = ApplicationRepository(second).get_application(record_id)
    assert loaded is not None
    assert loaded.company_name == "甲公司"
    second.close()

