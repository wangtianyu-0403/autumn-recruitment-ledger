from __future__ import annotations

import sqlite3
from pathlib import Path

from recruitment_ledger.database import Database
from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.repository import ApplicationRepository


def table_names(database: Database) -> set[str]:
    rows = database.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def create_version_one_database(path: Path, *, with_manual_order: bool = False) -> None:
    connection = sqlite3.connect(path)
    manual_order_column = (
        ", manual_order INTEGER NOT NULL DEFAULT 0" if with_manual_order else ""
    )
    connection.executescript(
        f"""
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            position_name TEXT NOT NULL,
            job_description TEXT NOT NULL DEFAULT '',
            application_date TEXT NOT NULL,
            status TEXT NOT NULL,
            company_url TEXT NOT NULL DEFAULT '',
            recruitment_url TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL DEFAULT '',
            salary TEXT NOT NULL DEFAULT '',
            contact_name TEXT NOT NULL DEFAULT '',
            contact_info TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            follow_up_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0
            {manual_order_column}
        );
        PRAGMA user_version = 1;
        """
    )
    connection.executemany(
        """
        INSERT INTO applications (
            company_name, position_name, application_date, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("甲公司", "岗位甲", "2026-07-01", "已投递", "2026-07-01", "2026-07-02"),
            ("乙公司", "岗位乙", "2026-07-01", "已投递", "2026-07-01", "2026-07-03"),
            ("丙公司", "岗位丙", "2026-07-01", "已投递", "2026-07-01", "2026-07-03"),
        ],
    )
    connection.commit()
    connection.close()


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


def test_version_one_database_migrates_to_ordering_schema(tmp_path: Path) -> None:
    path = tmp_path / "version-one.db"
    create_version_one_database(path)

    database = Database(path)
    database.initialize()

    columns = {
        row["name"]
        for row in database.connection.execute("PRAGMA table_info(applications)")
    }
    rows = database.connection.execute(
        "SELECT id, is_pinned, manual_order FROM applications ORDER BY manual_order"
    ).fetchall()
    assert {"is_pinned", "manual_order"} <= columns
    assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert [row["id"] for row in rows] == [3, 2, 1]
    assert all(row["is_pinned"] == 0 for row in rows)
    database.close()


def test_ordering_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "version-one.db"
    create_version_one_database(path)
    database = Database(path)

    database.initialize()
    first_orders = database.connection.execute(
        "SELECT id, manual_order FROM applications ORDER BY id"
    ).fetchall()
    database.initialize()
    second_orders = database.connection.execute(
        "SELECT id, manual_order FROM applications ORDER BY id"
    ).fetchall()

    assert [tuple(row) for row in second_orders] == [tuple(row) for row in first_orders]
    database.close()


def test_ordering_migration_completes_partially_added_columns(tmp_path: Path) -> None:
    path = tmp_path / "partial-version-one.db"
    create_version_one_database(path, with_manual_order=True)

    database = Database(path)
    database.initialize()

    columns = {
        row["name"]
        for row in database.connection.execute("PRAGMA table_info(applications)")
    }
    rows = database.connection.execute(
        "SELECT id, is_pinned, manual_order FROM applications ORDER BY manual_order"
    ).fetchall()
    assert {"is_pinned", "manual_order"} <= columns
    assert [row["id"] for row in rows] == [3, 2, 1]
    assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 2
    database.close()
