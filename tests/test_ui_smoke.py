from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from autumn_ledger.backup import BackupManager
from autumn_ledger.models import ApplicationRecord
from autumn_ledger.paths import AppPaths
from autumn_ledger.services import ApplicationService
from autumn_ledger.update import ReleaseInfo
from autumn_ledger.ui.application_dialog import ApplicationDialog
from autumn_ledger.ui import main_window
from autumn_ledger.ui.main_window import MainWindow


def test_main_window_contains_required_controls(
    qtbot,
    service: ApplicationService,
    app_paths: AppPaths,
    database,
) -> None:
    service.create(
        ApplicationRecord(
            company_name="示例科技",
            position_name="Python 开发工程师",
            application_date="2026-07-26",
            status="已投递",
        )
    )
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    window.show()

    assert window.add_button.text() == "新增公司/岗位"
    assert window.search_edit.placeholderText()
    assert window.status_filter.itemText(0) == "全部状态"
    assert window.table.rowCount() == 1
    assert window.version_label.objectName() == "versionLabel"
    assert window.version_label.text() == "版本v1.1.1"
    assert window.statusBar().isAncestorOf(window.version_label)
    assert window.check_update_button.text() == "检查更新"


def test_manual_update_check_reports_current_version(
    qtbot,
    monkeypatch,
    service: ApplicationService,
    app_paths: AppPaths,
    database,
) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main_window,
        "fetch_latest_release",
        lambda: ReleaseInfo(
            version=(1, 1, 1),
            tag_name="v1.1.1",
            asset_url="https://example.invalid/update.zip",
            asset_digest="sha256:" + "a" * 64,
            html_url="https://example.invalid/v1.1.1",
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, message: messages.append((title, message)),
    )
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)

    window.check_for_updates()

    assert messages == [("检查更新", "当前已是最新版本（v1.1.1）。")]


def test_source_mode_never_installs_newer_release(
    qtbot,
    monkeypatch,
    service: ApplicationService,
    app_paths: AppPaths,
    database,
) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        main_window,
        "fetch_latest_release",
        lambda: ReleaseInfo(
            version=(1, 2, 0),
            tag_name="v1.2.0",
            asset_url="https://example.invalid/update.zip",
            asset_digest="sha256:" + "b" * 64,
            html_url="https://example.invalid/v1.2.0",
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, message: messages.append(message),
    )
    monkeypatch.setattr(
        main_window,
        "download_release_asset",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("源码模式不得下载或安装更新")
        ),
    )
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)

    window.check_for_updates()

    assert messages == ["源码运行模式请使用 scripts\\sync_local_windows.bat 更新本地程序。"]


def test_application_dialog_can_be_created(qtbot) -> None:
    dialog = ApplicationDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "新增公司/岗位"
    assert dialog.company_edit.objectName() == "company_name"
    assert dialog.position_edit.objectName() == "position_name"


def test_application_dialog_blocks_empty_required_fields(
    qtbot, monkeypatch
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )
    dialog = ApplicationDialog()
    qtbot.addWidget(dialog)
    save_button = dialog.findChild(QDialogButtonBox).button(
        QDialogButtonBox.StandardButton.Save
    )

    qtbot.mouseClick(save_button, Qt.MouseButton.LeftButton)

    assert dialog.result() == 0
    assert warnings
    assert "公司名称不能为空" in warnings[0]
