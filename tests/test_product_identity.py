from __future__ import annotations

from recruitment_ledger.backup import BackupManager
from recruitment_ledger.ui.main_window import MainWindow


def test_renamed_application_exposes_new_identity(
    qtbot, service, app_paths, database
) -> None:
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)

    assert window.windowTitle() == "招聘记录台账"
    assert window.version_label.text() == "版本v1.1.2"


def test_renamed_entrypoint_is_importable() -> None:
    import recruitment_ledger
    from main import run

    assert recruitment_ledger.__doc__ == "招聘记录台账。"
    assert callable(run)


def test_renamed_package_exposes_current_version() -> None:
    import recruitment_ledger

    assert recruitment_ledger.__version__ == "1.1.2"
