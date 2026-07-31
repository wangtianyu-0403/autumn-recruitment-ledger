from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def legacy_data_root(new_root: Path) -> Path:
    """Return the previous application-data directory beside ``new_root``."""
    return new_root.expanduser().resolve().parent / "AutumnRecruitmentLedger"


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    data_dir: Path
    database_path: Path
    backups_dir: Path
    exports_dir: Path
    logs_dir: Path
    log_path: Path

    @classmethod
    def from_standard_paths(cls) -> "AppPaths":
        location = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not location:
            raise OSError("系统未提供可写的应用数据目录。")
        return cls.from_root(Path(location))

    @classmethod
    def from_root(cls, root: Path) -> "AppPaths":
        resolved = root.expanduser().resolve()
        data_dir = resolved / "data"
        logs_dir = resolved / "logs"
        return cls(
            root=resolved,
            data_dir=data_dir,
            database_path=data_dir / "autumn_recruitment.db",
            backups_dir=resolved / "backups",
            exports_dir=resolved / "exports",
            logs_dir=logs_dir,
            log_path=logs_dir / "autumn_ledger.log",
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.root,
            self.data_dir,
            self.backups_dir,
            self.exports_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
