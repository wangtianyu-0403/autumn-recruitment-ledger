from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .constants import MAX_AUTO_BACKUPS
from .database import Database
from .paths import AppPaths


class BackupError(RuntimeError):
    """备份或恢复错误。"""


class BackupManager:
    def __init__(self, database: Database, paths: AppPaths) -> None:
        self.database = database
        self.paths = paths

    def create_backup(self, destination: Path) -> Path:
        target = destination.expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target == self.database.path:
                raise BackupError("备份文件不能与当前数据库相同。")
            with closing(sqlite3.connect(target)) as target_connection:
                self.database.connection.backup(target_connection)
            return target
        except BackupError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise BackupError(f"备份数据库失败:{exc}") from exc

    def create_daily_backup(self, now: datetime | None = None) -> Path | None:
        current = now or datetime.now()
        target = self.paths.backups_dir / f"recruitment_record_{current:%Y%m%d}.db"
        if target.exists():
            self.cleanup_auto_backups()
            return None
        backup = self.create_backup(target)
        self.cleanup_auto_backups()
        return backup

    def cleanup_auto_backups(self, max_count: int = MAX_AUTO_BACKUPS) -> None:
        files = sorted(
            {
                *self.paths.backups_dir.glob("autumn_recruitment_????????.db"),
                *self.paths.backups_dir.glob("recruitment_record_????????.db"),
            },
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old_file in files[max_count:]:
            old_file.unlink(missing_ok=True)

    def validate_backup(self, source: Path) -> None:
        candidate = source.expanduser().resolve()
        if not candidate.is_file():
            raise BackupError("恢复文件不存在。")
        try:
            uri = f"{candidate.as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise BackupError("恢复文件未通过SQLite完整性检查。")
                table = connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'applications'
                    """
                ).fetchone()
                if table is None:
                    raise BackupError("恢复文件缺少 applications 表。")
        except BackupError:
            raise
        except sqlite3.Error as exc:
            raise BackupError(f"恢复文件不是有效的SQLite数据库:{exc}") from exc

    def restore_database(self, source: Path) -> Path:
        self.validate_backup(source)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safety_backup = self.paths.backups_dir / f"pre_restore_{timestamp}.db"
        self.create_backup(safety_backup)

        temporary = self.database.path.with_name(f".restore_{timestamp}.db")
        previous = self.database.path.with_name(f".previous_{timestamp}.db")
        try:
            with closing(sqlite3.connect(source)) as source_connection, closing(
                sqlite3.connect(temporary)
            ) as temp_connection:
                source_connection.backup(temp_connection)
            self.database.close()
            if self.database.path.exists():
                os.replace(self.database.path, previous)
            os.replace(temporary, self.database.path)
            self._remove_sidecars()
            self.database.reconnect()
            previous.unlink(missing_ok=True)
            return safety_backup
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            self.database.close()
            temporary.unlink(missing_ok=True)
            if previous.exists():
                if self.database.path.exists():
                    self.database.path.unlink(missing_ok=True)
                os.replace(previous, self.database.path)
            try:
                self.database.reconnect()
            except RuntimeError as reconnect_error:
                raise BackupError(
                    f"恢复失败且数据库重新连接失败:{reconnect_error}"
                ) from exc
            raise BackupError(f"恢复数据库失败,已尝试保留原数据:{exc}") from exc

    def _remove_sidecars(self) -> None:
        for suffix in ("-wal", "-shm"):
            Path(f"{self.database.path}{suffix}").unlink(missing_ok=True)
