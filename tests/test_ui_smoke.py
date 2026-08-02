from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from recruitment_ledger.backup import BackupManager
from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.paths import AppPaths
from recruitment_ledger.repository import SortMode
from recruitment_ledger.services import ApplicationService
from recruitment_ledger.update import ReleaseInfo
from recruitment_ledger.ui import main_window
from recruitment_ledger.ui.application_dialog import ApplicationDialog
from recruitment_ledger.ui.application_table import ApplicationTableWidget
from recruitment_ledger.ui.main_window import MainWindow


def _isolated_settings(monkeypatch, tmp_path, initial=None) -> QSettings:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.clear()
    for key, value in (initial or {}).items():
        settings.setValue(key, value)
    settings.sync()
    monkeypatch.setattr(main_window, "QSettings", lambda: settings)
    return settings


def _create_record(
    service: ApplicationService,
    company: str,
    application_date: str,
) -> int:
    return service.create(
        ApplicationRecord(
            company_name=company,
            position_name="工程师",
            application_date=application_date,
            status="已投递",
        )
    )


def _visible_companies(window: MainWindow) -> list[str]:
    return [window.table.item(row, 0).text() for row in range(window.table.rowCount())]


def test_window_exposes_three_sort_modes_and_uses_draggable_table(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)

    assert isinstance(window.table, ApplicationTableWidget)
    assert [
        window.sort_mode_combo.itemText(index)
        for index in range(window.sort_mode_combo.count())
    ] == ["手动排序", "按投递时间", "按最后更新时间"]
    assert window.sort_mode_combo.currentData() == SortMode.UPDATED_AT.value


def test_sort_mode_settings_accept_only_enum_values(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    settings = _isolated_settings(
        monkeypatch, tmp_path, {"table/sort_mode": "按投递时间"}
    )
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)

    assert window.sort_mode_combo.currentData() == SortMode.UPDATED_AT.value

    window.sort_mode_combo.setCurrentIndex(
        window.sort_mode_combo.findData(SortMode.APPLICATION_DATE.value)
    )
    window.close()
    assert settings.value("table/sort_mode") == SortMode.APPLICATION_DATE.value


def test_automatic_drag_switches_to_manual_and_rebuilds_visible_rows(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    older_id = _create_record(service, "较早公司", "2026-01-01")
    newer_id = _create_record(service, "较晚公司", "2026-02-01")
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    window.sort_mode_combo.setCurrentIndex(
        window.sort_mode_combo.findData(SortMode.APPLICATION_DATE.value)
    )

    assert window.table.apply_row_move(0, 1)

    assert window.sort_mode_combo.currentData() == SortMode.MANUAL.value
    qtbot.waitUntil(lambda: not window._table_refresh_timer.isActive())
    assert [record.id for record in window._records] == [older_id, newer_id]
    assert _visible_companies(window) == ["较早公司", "较晚公司"]


def test_selecting_application_date_sort_refreshes_visible_order(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    _create_record(service, "较晚公司", "2026-02-01")
    _create_record(service, "较早公司", "2026-01-01")
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)

    window.sort_mode_combo.setCurrentIndex(
        window.sort_mode_combo.findData(SortMode.APPLICATION_DATE.value)
    )

    assert _visible_companies(window) == ["较晚公司", "较早公司"]


def test_failed_drag_reports_error_and_restores_database_order(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    first_id = _create_record(service, "甲公司", "2026-01-01")
    second_id = _create_record(service, "乙公司", "2026-02-01")
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    original = _visible_companies(window)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, message: errors.append((title, message)),
    )
    monkeypatch.setattr(
        service,
        "reorder_visible",
        lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    window._rows_reordered([first_id, second_id])

    assert window.sort_mode_combo.currentData() == SortMode.UPDATED_AT.value
    qtbot.waitUntil(lambda: not window._table_refresh_timer.isActive())
    assert _visible_companies(window) == original
    assert errors and "排序" in errors[0][0]


def test_drag_refresh_runs_after_native_move_cleanup(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    first = _create_record(service, "甲公司", "2026-01-01")
    second = _create_record(service, "乙公司", "2026-01-02")
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    window.sort_mode_combo.setCurrentIndex(
        window.sort_mode_combo.findData(SortMode.MANUAL.value)
    )

    window._rows_reordered([first, second])
    for column in (0, 1, 2, 4, 5, 7):
        window.table.takeItem(0, column)

    qtbot.waitUntil(lambda: window.table.item(0, 0) is not None)

    assert all(window.table.item(0, column) is not None for column in (0, 1, 2, 4, 5, 7))
    assert window.table.cellWidget(0, 3) is not None
    assert window.table.cellWidget(0, 6) is not None
    assert window.table.cellWidget(0, 8) is not None


def test_failed_drag_queues_refresh_after_native_move_cleanup(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    first = _create_record(service, "甲公司", "2026-01-01")
    second = _create_record(service, "乙公司", "2026-01-02")
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    original_ids = [record.id for record in window._records]
    monkeypatch.setattr(
        service,
        "reorder_visible",
        lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)

    window._rows_reordered([second, first])
    for column in (0, 1, 2, 4, 5, 7):
        window.table.takeItem(0, column)

    qtbot.waitUntil(lambda: window.table.item(0, 0) is not None)

    assert [record.id for record in window._records] == original_ids
    assert all(window.table.item(0, column) is not None for column in (0, 1, 2, 4, 5, 7))


def test_pin_action_keeps_timestamp_and_refreshes_marker_and_button(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    application_id = _create_record(service, "置顶公司", "2026-01-01")
    database.connection.execute(
        "UPDATE applications SET updated_at = ? WHERE id = ?",
        ("2000-01-01 00:00:00", application_id),
    )
    database.connection.commit()
    previous = service.get(application_id).updated_at
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)

    qtbot.mouseClick(
        window.table.cellWidget(0, 8).pin_button,
        Qt.MouseButton.LeftButton,
    )

    assert service.get(application_id).updated_at == previous
    assert window.table.item(0, 0).text() == "📌 置顶公司"
    assert window.table.cellWidget(0, 8).pin_button.text() == "取消置顶"


def test_filtered_drag_preserves_hidden_rows(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    first = _create_record(service, "目标甲", "2026-01-01")
    hidden = _create_record(service, "隐藏公司", "2026-01-02")
    second = _create_record(service, "目标乙", "2026-01-03")
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    window.search_edit.setText("目标")
    window.search_timer.stop()
    window.refresh_data()

    window._rows_reordered([first, second])
    window.search_edit.clear()
    window.search_timer.stop()
    window.refresh_data()

    assert [record.id for record in window._records] == [first, hidden, second]


def test_export_uses_current_screen_order(
    qtbot, monkeypatch, tmp_path, service, app_paths, database
) -> None:
    _isolated_settings(monkeypatch, tmp_path)
    _create_record(service, "较早公司", "2026-01-01")
    _create_record(service, "较晚公司", "2026-02-01")
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    captured: list[list[ApplicationRecord]] = []
    output = tmp_path / "records.csv"
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getSaveFileName",
        lambda *args: (str(output), "CSV 文件 (*.csv)"),
    )
    monkeypatch.setattr(
        main_window,
        "export_applications_to_csv",
        lambda records, destination: captured.append(records) or destination,
    )

    window.export_current()

    assert captured == [window._records]
    assert [record.company_name for record in captured[0]] == ["较晚公司", "较早公司"]


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
    action_cell = window.table.cellWidget(0, 8)
    assert window.table.columnWidth(8) >= 230
    assert window.table.columnWidth(8) >= action_cell.minimumSizeHint().width()
    assert window.version_label.objectName() == "versionLabel"
    assert window.version_label.text() == "版本v1.1.2"
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
            version=(1, 1, 2),
            tag_name="v1.1.2",
            asset_url="https://example.invalid/update.zip",
            asset_digest="sha256:" + "a" * 64,
            html_url="https://example.invalid/v1.1.2",
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

    assert messages == [("检查更新", "当前已是最新版本（v1.1.2）。")]


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
