from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import recruitment_ledger.data_migration as data_migration
from recruitment_ledger.data_migration import DataMigrationError, migrate_legacy_data
from recruitment_ledger.paths import AppPaths, legacy_data_root


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


def test_concurrent_migrations_publish_one_verified_database_from_unique_temporaries(
    tmp_path: Path,
) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    source = create_legacy_database(old_paths.database_path, company="并发迁移记录")
    source.execute("CREATE TABLE migration_padding (payload BLOB NOT NULL)")
    source.execute(
        "INSERT INTO migration_padding (payload) VALUES (zeroblob(?))",
        (16 * 1024 * 1024,),
    )
    source.commit()
    source.close()
    new_paths.data_dir.mkdir(parents=True)
    unrelated_file = new_paths.data_dir / ".migration.db"
    unrelated_file.write_bytes(b"not owned by the migrator")
    start = threading.Barrier(2)

    def migrate_concurrently() -> bool:
        start.wait(timeout=10)
        return migrate_legacy_data(new_paths, old_paths.root)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(migrate_concurrently) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]

    assert results.count(True) == 1
    assert results.count(False) == 1
    with sqlite3.connect(new_paths.database_path) as migrated:
        assert migrated.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert read_company(new_paths.database_path) == "并发迁移记录"
    assert unrelated_file.read_bytes() == b"not owned by the migrator"
    assert not list(new_paths.data_dir.glob(".migration-*.db"))


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


def test_attachment_created_during_copy_wins_without_being_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "legacy-backups"
    destination = tmp_path / "new-backups"
    source.mkdir()
    destination.mkdir()
    source_file = source / "shared-backup.db"
    destination_file = destination / source_file.name
    source_file.write_bytes(b"legacy attachment")
    competing_content = b"newer attachment created during migration"
    original_copy2 = data_migration.shutil.copy2
    race_injected = False

    def copy_after_competing_destination(
        copy_source: Path, copy_destination: Path
    ) -> str:
        nonlocal race_injected
        destination_file.write_bytes(competing_content)
        race_injected = True
        return str(original_copy2(copy_source, copy_destination))

    monkeypatch.setattr(data_migration.shutil, "copy2", copy_after_competing_destination)

    data_migration._copy_directory_contents(source, destination)

    assert race_injected
    assert destination_file.read_bytes() == competing_content
    assert not [path for path in destination.iterdir() if path != destination_file]
