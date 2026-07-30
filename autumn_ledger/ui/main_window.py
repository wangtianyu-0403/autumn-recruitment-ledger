from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..backup import BackupError, BackupManager
from ..constants import (
    APP_DISPLAY_NAME,
    APP_VERSION,
    APPLICATION_STATUSES,
    STATUS_COLORS,
)
from ..export import (
    EmptyExportError,
    ExportError,
    default_export_filename,
    export_applications_to_csv,
)
from ..models import ApplicationRecord
from ..paths import AppPaths
from ..services import ApplicationService
from .application_dialog import ApplicationDialog
from .history_dialog import HistoryDialog
from .recycle_bin_dialog import RecycleBinDialog
from .widgets import ActionCell, StatisticCard


class MainWindow(QMainWindow):
    TABLE_HEADERS = (
        "公司名称",
        "岗位名称",
        "投递时间",
        "当前进度",
        "工作地点",
        "投递渠道",
        "公司官网",
        "最后更新",
        "操作",
    )

    def __init__(
        self,
        service: ApplicationService,
        backup_manager: BackupManager,
        paths: AppPaths,
    ) -> None:
        super().__init__()
        self.service = service
        self.backup_manager = backup_manager
        self.paths = paths
        self.settings = QSettings()
        self._records: list[ApplicationRecord] = []
        self._build_ui()
        self._restore_settings()
        self.refresh_data()

    def _build_ui(self) -> None:
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1200, 760)
        self.setMinimumSize(920, 620)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 14, 18, 18)
        layout.setSpacing(14)
        cards = QHBoxLayout()
        self.stat_cards = {
            "全部岗位": StatisticCard("全部岗位"),
            "已投递": StatisticCard("已投递"),
            "面试进行中": StatisticCard("面试进行中"),
            "已有Offer": StatisticCard("已有 Offer"),
        }
        for card in self.stat_cards.values():
            cards.addWidget(card)
        layout.addLayout(cards)

        self.table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.table.setObjectName("applications_table")
        self.table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        for index, width in enumerate((155, 180, 95, 135, 105, 105, 90, 145, 190)):
            self.table.setColumnWidth(index, width)
        self.table.cellDoubleClicked.connect(self._edit_row)
        layout.addWidget(self.table)

        self.empty_label = QLabel("暂无岗位记录，点击“新增公司/岗位”开始记录。")
        self.empty_label.setObjectName("empty_label")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)
        self.setCentralWidget(central)
        self._build_toolbar()
        self.statusBar().showMessage("就绪")
        self.version_label = QLabel(f"版本v{APP_VERSION}", self)
        self.version_label.setObjectName("versionLabel")
        self.statusBar().addPermanentWidget(self.version_label)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.refresh_data)
        self.search_edit.textChanged.connect(lambda: self.search_timer.start())
        self.status_filter.currentTextChanged.connect(self.refresh_data)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.add_button = QPushButton("新增公司/岗位")
        self.add_button.setObjectName("add_button")
        self.add_button.setProperty("primary", True)
        self.add_button.clicked.connect(self.add_application)
        toolbar.addWidget(self.add_button)
        toolbar.addSeparator()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("search_edit")
        self.search_edit.setPlaceholderText("搜索公司、岗位、地点或备注")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(225)
        toolbar.addWidget(self.search_edit)
        self.status_filter = QComboBox()
        self.status_filter.setObjectName("status_filter")
        self.status_filter.addItem("全部状态")
        self.status_filter.addItems(APPLICATION_STATUSES)
        self.status_filter.setMinimumWidth(125)
        toolbar.addWidget(self.status_filter)
        for text, callback in (
            ("刷新", self.refresh_data),
            ("导出 CSV", self.export_current),
            ("备份数据库", self.manual_backup),
            ("恢复数据库", self.restore_database),
            ("回收站", self.open_recycle_bin),
            ("打开数据目录", self.open_data_directory),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            toolbar.addWidget(button)

    def _restore_settings(self) -> None:
        geometry = self.settings.value("window/geometry", QByteArray())
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
        status = str(self.settings.value("filters/status", "全部状态"))
        index = self.status_filter.findText(status)
        if index >= 0:
            self.status_filter.setCurrentIndex(index)
        widths = self.settings.value("table/column_widths")
        if isinstance(widths, list) and len(widths) == self.table.columnCount():
            for column, width in enumerate(widths):
                self.table.setColumnWidth(column, int(width))

    def refresh_data(self) -> None:
        selected = self.status_filter.currentText()
        status = None if selected == "全部状态" else selected
        try:
            self._records = self.service.list(self.search_edit.text().strip(), status)
            self._populate_table()
            self._refresh_statistics()
            self.statusBar().showMessage(f"共显示 {len(self._records)} 条记录", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "读取失败", f"无法读取岗位数据：{exc}")

    def _refresh_statistics(self) -> None:
        statistics = self.service.statistics()
        for name, card in self.stat_cards.items():
            card.set_value(statistics[name])

    def _populate_table(self) -> None:
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            for column, value in (
                (0, record.company_name),
                (1, record.position_name),
                (2, record.application_date),
                (4, record.location or "—"),
                (5, record.channel or "—"),
                (7, record.updated_at),
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))
            self._add_status_combo(row, record)
            self._add_url_button(row, record)
            self._add_action_cell(row, record)
        self.table.setUpdatesEnabled(True)
        self.table.setVisible(bool(self._records))
        self.empty_label.setVisible(not self._records)

    def _add_status_combo(self, row: int, record: ApplicationRecord) -> None:
        combo = QComboBox()
        combo.addItems(APPLICATION_STATUSES)
        combo.setCurrentText(record.status)
        combo.setStyleSheet(
            f"QComboBox {{ background-color: {STATUS_COLORS.get(record.status, '#FFFFFF')}; }}"
        )
        combo.currentTextChanged.connect(
            lambda value, app_id=record.id, old=record.status, widget=combo:
            self._change_status(app_id, old, value, widget)
        )
        self.table.setCellWidget(row, 3, combo)

    def _change_status(
        self,
        application_id: int | None,
        old_status: str,
        new_status: str,
        combo: QComboBox,
    ) -> None:
        if application_id is None or old_status == new_status:
            return
        try:
            self.service.update_status(application_id, new_status)
        except Exception as exc:
            combo.blockSignals(True)
            combo.setCurrentText(old_status)
            combo.blockSignals(False)
            QMessageBox.critical(self, "修改失败", f"无法修改岗位状态：{exc}")
            return
        self.statusBar().showMessage("岗位状态已更新", 3000)
        QTimer.singleShot(0, self.refresh_data)

    def _add_url_button(self, row: int, record: ApplicationRecord) -> None:
        button = QPushButton("打开官网" if record.company_url else "未填写")
        button.setEnabled(bool(record.company_url))
        if record.company_url:
            button.clicked.connect(
                lambda checked=False, url=record.company_url: self._open_url(url)
            )
        self.table.setCellWidget(row, 6, button)

    def _open_url(self, url: str) -> None:
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, "打开失败", "无法调用默认浏览器打开该网址。")

    def _add_action_cell(self, row: int, record: ApplicationRecord) -> None:
        if record.id is None:
            return
        actions = ActionCell(record.id)
        actions.edit_requested.connect(self.edit_application)
        actions.history_requested.connect(self.show_history)
        actions.delete_requested.connect(self.delete_application)
        self.table.setCellWidget(row, 8, actions)

    def _edit_row(self, row: int, column: int) -> None:
        del column
        if 0 <= row < len(self._records) and self._records[row].id is not None:
            self.edit_application(self._records[row].id)

    def add_application(self) -> None:
        dialog = ApplicationDialog(
            parent=self,
            save_callback=lambda record: self.service.create(record),
        )
        if dialog.exec():
            self.refresh_data()

    def edit_application(self, application_id: int) -> None:
        record = self.service.get(application_id)
        if record is None or record.is_deleted:
            QMessageBox.warning(self, "记录不存在", "该岗位已被删除，请刷新列表。")
            self.refresh_data()
            return
        dialog = ApplicationDialog(
            record=record,
            parent=self,
            save_callback=self.service.update,
        )
        if dialog.exec():
            self.refresh_data()

    def show_history(self, application_id: int) -> None:
        record = self.service.get(application_id)
        if record is None:
            QMessageBox.warning(self, "记录不存在", "该岗位已被删除。")
            return
        HistoryDialog(record, self.service.history(application_id), self).exec()

    def delete_application(self, application_id: int) -> None:
        record = self.service.get(application_id)
        if record is None:
            QMessageBox.warning(self, "记录不存在", "该岗位已被删除。")
            return
        answer = QMessageBox.question(
            self,
            "确认删除",
            f"确定将“{record.company_name} - {record.position_name}”移入回收站吗？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.soft_delete(application_id)
            self.refresh_data()
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", f"无法删除岗位：{exc}")

    def export_current(self) -> None:
        if not self._records:
            QMessageBox.information(self, "没有可导出数据", "当前筛选结果为空。")
            return
        recent = Path(str(self.settings.value("paths/export", self.paths.exports_dir)))
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "导出 CSV",
            str(recent / default_export_filename()),
            "CSV 文件 (*.csv)",
        )
        if not selected:
            return
        try:
            result = export_applications_to_csv(self._records, Path(selected))
            self.settings.setValue("paths/export", str(result.parent))
            QMessageBox.information(self, "导出成功", f"CSV 已保存到：\n{result}")
        except (EmptyExportError, ExportError) as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def manual_backup(self) -> None:
        filename = f"autumn_recruitment_manual_{datetime.now():%Y%m%d_%H%M%S}.db"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "备份数据库",
            str(self.paths.backups_dir / filename),
            "SQLite 数据库 (*.db)",
        )
        if not selected:
            return
        try:
            result = self.backup_manager.create_backup(Path(selected))
            QMessageBox.information(self, "备份成功", f"数据库已备份到：\n{result}")
        except BackupError as exc:
            QMessageBox.critical(self, "备份失败", str(exc))

    def restore_database(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择备份数据库",
            str(self.paths.backups_dir),
            "SQLite 数据库 (*.db)",
        )
        if not selected:
            return
        source = Path(selected)
        try:
            self.backup_manager.validate_backup(source)
        except BackupError as exc:
            QMessageBox.critical(self, "恢复文件无效", str(exc))
            return
        answer = QMessageBox.warning(
            self,
            "确认恢复数据库",
            "恢复将替换当前全部招聘数据。程序会先自动备份当前数据库，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.backup_manager.restore_database(source)
            self.refresh_data()
            QMessageBox.information(self, "恢复成功", "数据库已恢复并重新连接。")
        except BackupError as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))

    def open_recycle_bin(self) -> None:
        RecycleBinDialog(self.service, self).exec()
        self.refresh_data()

    def open_data_directory(self) -> None:
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.paths.root))):
            QMessageBox.warning(self, "打开失败", "无法使用系统文件管理器打开数据目录。")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("filters/status", self.status_filter.currentText())
        self.settings.setValue(
            "table/column_widths",
            [self.table.columnWidth(i) for i in range(self.table.columnCount())],
        )
        self.settings.sync()
        super().closeEvent(event)
