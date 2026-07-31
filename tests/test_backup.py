from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from autumn_ledger.backup import BackupError, BackupManager
from autumn_ledger.database import Database
from autumn_ledger.models import ApplicationRecord
from autumn_ledger.paths import AppPaths
from autumn_ledger.repository import ApplicationRepository


def test_create_backup_contains_data(
    database: Database,
    app_paths: AppPaths,
) -> None:
    ApplicationRepository(database).create_application(
        ApplicationRecord("备份公司", "测试岗位", "2026-07-26", "已投递")
    )
    target = app_paths.backups_dir / "manual.db"
    BackupManager(database, app_paths).create_backup(target)
    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 1


def test_auto_backup_cleanup_keeps_thirty(
    database: Database,
    app_paths: AppPaths,
) -> None:
    manager = BackupManager(database, app_paths)
    base = datetime(2026, 1, 1)
    for day in range(35):
        manager.create_daily_backup(base + timedelta(days=day))
    assert len(list(app_paths.backups_dir.glob("recruitment_record_????????.db"))) == 30


def test_cleanup_counts_old_and_new_daily_backups_together(
    database: Database, app_paths: AppPaths
) -> None:
    manager = BackupManager(database, app_paths)
    base = datetime(2026, 1, 1)
    for day in range(20):
        date = base + timedelta(days=day)
        (app_paths.backups_dir / f"autumn_recruitment_{date:%Y%m%d}.db").write_bytes(
            b"legacy"
        )
        (app_paths.backups_dir / f"recruitment_record_{date:%Y%m%d}.db").write_bytes(
            b"current"
        )

    manager.cleanup_auto_backups(max_count=30)

    assert len(list(app_paths.backups_dir.glob("*.db"))) == 30


def test_paths_use_renamed_log_filename(app_paths: AppPaths) -> None:
    assert app_paths.log_path.name == "recruitment_ledger.log"


def test_invalid_restore_file_is_rejected(
    database: Database,
    app_paths: AppPaths,
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.db"
    invalid.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(BackupError):
        BackupManager(database, app_paths).validate_backup(invalid)


def test_restore_replaces_database(
    database: Database,
    app_paths: AppPaths,
    tmp_path: Path,
) -> None:
    repository = ApplicationRepository(database)
    repository.create_application(
        ApplicationRecord("原公司", "原岗位", "2026-07-26", "待投递")
    )
    other_path = tmp_path / "other.db"
    other_database = Database(other_path)
    other_database.initialize()
    ApplicationRepository(other_database).create_application(
        ApplicationRecord("新公司", "新岗位", "2026-07-27", "已有Offer")
    )
    other_database.close()

    BackupManager(database, app_paths).restore_database(other_path)
    records = repository.list_applications()
    assert [record.company_name for record in records] == ["新公司"]
