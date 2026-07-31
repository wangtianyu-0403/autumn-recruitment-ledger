from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class DatabaseError(RuntimeError):
    """数据库初始化或连接错误。"""


class Database:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self.connect()
        if self._connection is None:
            raise DatabaseError("数据库连接不可用。")
        return self._connection

    def connect(self) -> None:
        if self._connection is not None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=10.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 10000")
            self._connection = connection
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError(f"无法打开数据库:{exc}") from exc

    def initialize(self) -> None:
        connection = self.connection
        try:
            with connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS applications (
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
                    );

                    CREATE TABLE IF NOT EXISTS status_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        application_id INTEGER NOT NULL,
                        old_status TEXT,
                        new_status TEXT NOT NULL,
                        changed_at TEXT NOT NULL,
                        notes TEXT NOT NULL DEFAULT '',
                        FOREIGN KEY(application_id) REFERENCES applications(id)
                            ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_applications_deleted_updated
                    ON applications(is_deleted, updated_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_applications_status
                    ON applications(status);

                    CREATE INDEX IF NOT EXISTS idx_status_history_application
                    ON status_history(application_id, changed_at);
                    """
                )
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version < self.SCHEMA_VERSION:
                    connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        except sqlite3.Error as exc:
            raise DatabaseError(f"数据库初始化失败:{exc}") from exc

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connection
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def reconnect(self) -> None:
        self.close()
        self.connect()
        self.initialize()

    def foreign_keys_enabled(self) -> bool:
        return bool(self.connection.execute("PRAGMA foreign_keys").fetchone()[0])

    def __enter__(self) -> "Database":
        self.connect()
        self.initialize()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

