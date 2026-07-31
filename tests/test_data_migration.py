from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import autumn_ledger.data_migration as data_migration
from autumn_ledger.data_migration import DataMigrationError, migrate_legacy_data
from autumn_ledger.paths import AppPaths, legacy_data_root


def create_legacy_database(path: Path, company: str) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("CREATE TABLE applications (company_name TEXT NOT NULL)")
    connection.execute("INSERT INTO applications (company_name) VALUES (?)", (company,))
    connection.commit()
    return connection


def read_company(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT company_name FROM applications").fetchone()
    assert row is not None
    return str(row[0])


def test_legacy_data_root_uses_legacy_sibling_application_directory(
    tmp_path: Path,
) -> None:
    new_root = tmp_path / "RecruitmentRecordLedger"

    assert legacy_data_root(new_root) == tmp_path / "AutumnRecruitmentLedger"


def test_new_user_without_legacy_data_keeps_new_directory_uncreated(tmp_path: Path) -> None:
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    old_root = tmp_path / "AutumnRecruitmentLedger"

    assert migrate_legacy_data(new_paths, old_root) is False
    assert not new_paths.root.exists()


def test_migrate_legacy_database_keeps_filename_source_and_committed_wal_content(
    tmp_path: Path,
) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    source = create_legacy_database(old_paths.database_path, company="旧记录")
    try:
        assert Path(f"{old_paths.database_path}-wal").exists()

        assert migrate_legacy_data(new_paths, old_paths.root) is True
    finally:
        source.close()

    assert new_paths.database_path.name == "autumn_recruitment.db"
    assert read_company(new_paths.database_path) == "旧记录"
    assert read_company(old_paths.database_path) == "旧记录"


def test_existing_new_database_is_never_overwritten(tmp_path: Path) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    old_source = create_legacy_database(old_paths.database_path, company="旧")
    old_source.close()
    new_source = create_legacy_database(new_paths.database_path, company="新")
    new_source.close()

    assert migrate_legacy_data(new_paths, old_paths.root) is False
    assert read_company(new_paths.database_path) == "新"


def test_database_created_after_preflight_is_never_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    old_source = create_legacy_database(old_paths.database_path, company="旧")
    old_source.close()
    original_copy = data_migration._copy_directory_contents
    competing_database_created = False

    def copy_and_create_competing_database(source: Path, destination: Path) -> None:
        nonlocal competing_database_created
        original_copy(source, destination)
        if not competing_database_created:
            competing_source = create_legacy_database(
                new_paths.database_path, company="新"
            )
            competing_source.close()
            competing_database_created = True

    monkeypatch.setattr(
        data_migration, "_copy_directory_contents", copy_and_create_competing_database
    )

    assert migrate_legacy_data(new_paths, old_paths.root) is False
    assert read_company(new_paths.database_path) == "新"
    assert not new_paths.database_path.with_name(".migration.db").exists()


def test_corrupt_legacy_database_does_not_leave_new_database(tmp_path: Path) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    old_paths.database_path.parent.mkdir(parents=True)
    old_paths.database_path.write_bytes(b"not sqlite")

    with pytest.raises(DataMigrationError):
        migrate_legacy_data(new_paths, old_paths.root)

    assert not new_paths.database_path.exists()
    assert old_paths.database_path.read_bytes() == b"not sqlite"


def test_migration_copies_only_missing_backup_and_export_files_without_logs(
    tmp_path: Path,
) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    source = create_legacy_database(old_paths.database_path, company="旧记录")
    old_paths.backups_dir.mkdir()
    old_paths.exports_dir.mkdir()
    old_paths.logs_dir.mkdir()
    (old_paths.backups_dir / "old-backup.db").write_bytes(b"legacy backup")
    (old_paths.backups_dir / "missing-backup.db").write_bytes(b"copied backup")
    (old_paths.exports_dir / "old-export.csv").write_text("legacy export", encoding="utf-8")
    (old_paths.exports_dir / "missing-export.csv").write_text(
        "copied export", encoding="utf-8"
    )
    (old_paths.logs_dir / "legacy.log").write_text("private", encoding="utf-8")
    new_paths.ensure_directories()
    (new_paths.backups_dir / "old-backup.db").write_bytes(b"new backup")
    (new_paths.exports_dir / "old-export.csv").write_text("new export", encoding="utf-8")
    try:
        assert migrate_legacy_data(new_paths, old_paths.root) is True
    finally:
        source.close()

    assert (new_paths.backups_dir / "old-backup.db").read_bytes() == b"new backup"
    assert (new_paths.exports_dir / "old-export.csv").read_text(encoding="utf-8") == "new export"
    assert (new_paths.backups_dir / "missing-backup.db").read_bytes() == b"copied backup"
    assert (new_paths.exports_dir / "missing-export.csv").read_text(
        encoding="utf-8"
    ) == "copied export"
    assert not (new_paths.logs_dir / "legacy.log").exists()
