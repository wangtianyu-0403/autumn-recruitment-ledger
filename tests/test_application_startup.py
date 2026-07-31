from __future__ import annotations

from pathlib import Path

import pytest

import recruitment_ledger.application as application
from recruitment_ledger.database import Database
from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.paths import AppPaths
from recruitment_ledger.repository import ApplicationRepository


def create_legacy_database(path: Path, company: str) -> None:
    database = Database(path)
    database.initialize()
    ApplicationRepository(database).create_application(
        ApplicationRecord(company, "测试岗位", "2026-07-30", "已投递")
    )
    database.close()


def test_legacy_root_from_standard_paths_uses_sibling_legacy_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    monkeypatch.setattr(AppPaths, "from_standard_paths", lambda: new_paths)

    assert AppPaths.legacy_root_from_standard_paths() == (
        tmp_path / "AutumnRecruitmentLedger"
    )


def test_startup_migrates_before_database_initialization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp: object
) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    create_legacy_database(old_paths.database_path, company="迁移记录")
    startup_databases: list[Database] = []

    def create_startup_database(path: Path) -> Database:
        database = Database(path)
        startup_databases.append(database)
        return database

    class Window:
        def show(self) -> None:
            return None

    monkeypatch.setattr(AppPaths, "from_standard_paths", lambda: new_paths)
    monkeypatch.setattr(application, "legacy_data_root", lambda root: old_paths.root)
    monkeypatch.setattr(application, "Database", create_startup_database)
    monkeypatch.setattr(application, "MainWindow", lambda *args: Window())

    try:
        assert application.run() == 0

        migrated = Database(new_paths.database_path)
        migrated.initialize()
        try:
            records = ApplicationRepository(migrated).list_applications()
        finally:
            migrated.close()
        assert [record.company_name for record in records] == ["迁移记录"]
    finally:
        for database in startup_databases:
            database.close()


def test_startup_migration_error_keeps_legacy_source_and_reports_its_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp: object
) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    old_paths.database_path.parent.mkdir(parents=True)
    old_paths.database_path.write_bytes(b"not sqlite")
    messages: list[str] = []

    def record_error(parent: object, title: str, message: str) -> None:
        messages.append(message)

    monkeypatch.setattr(AppPaths, "from_standard_paths", lambda: new_paths)
    monkeypatch.setattr(application, "legacy_data_root", lambda root: old_paths.root)
    monkeypatch.setattr(application.QMessageBox, "critical", record_error)

    assert application.run() == 1
    assert old_paths.database_path.read_bytes() == b"not sqlite"
    assert not new_paths.database_path.exists()
    assert len(messages) == 1
    assert str(old_paths.root) in messages[0]
    assert "旧数据已保留" in messages[0]
