from __future__ import annotations

import os
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from .paths import AppPaths


class DataMigrationError(RuntimeError):
    """旧版用户数据迁移失败。"""


def migrate_legacy_data(new_paths: AppPaths, old_root: Path) -> bool:
    """Atomically copy legacy local data into the current app-data directory."""
    old_paths = AppPaths.from_root(old_root)
    if new_paths.database_path.exists() or not old_paths.database_path.exists():
        return False

    new_paths.ensure_directories()
    try:
        with _owned_temporary_file(
            new_paths.data_dir, prefix=".migration-", suffix=".db"
        ) as temporary:
            source_uri = f"{old_paths.database_path.as_uri()}?mode=ro"
            with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(
                sqlite3.connect(temporary)
            ) as target:
                source.backup(target)
                integrity = target.execute("PRAGMA integrity_check").fetchone()
                if integrity is None or integrity[0] != "ok":
                    raise DataMigrationError("旧数据库未通过 SQLite 完整性检查。")
            _copy_directory_contents(old_paths.backups_dir, new_paths.backups_dir)
            _copy_directory_contents(old_paths.exports_dir, new_paths.exports_dir)
            try:
                os.link(temporary, new_paths.database_path)
            except FileExistsError:
                return False
            return True
    except DataMigrationError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise DataMigrationError(
            f"无法从“{old_paths.database_path}”迁移旧数据库：{exc}"
        ) from exc


def _copy_directory_contents(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    for source_file in source.iterdir():
        destination_file = destination / source_file.name
        if not source_file.is_file() or destination_file.exists():
            continue
        with _owned_temporary_file(
            destination, prefix=".attachment-", suffix=".tmp"
        ) as temporary:
            shutil.copy2(source_file, temporary)
            try:
                os.link(temporary, destination_file)
            except FileExistsError:
                continue


@contextmanager
def _owned_temporary_file(
    directory: Path, *, prefix: str, suffix: str
) -> Iterator[Path]:
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb", prefix=prefix, suffix=suffix, dir=directory, delete=False
        ) as handle:
            temporary = Path(handle.name)
        yield temporary
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
