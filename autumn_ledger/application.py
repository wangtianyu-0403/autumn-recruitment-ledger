from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from .backup import BackupError, BackupManager
from .constants import APPLICATION_NAME, APP_DISPLAY_NAME, ORGANIZATION_NAME
from .database import Database
from .logging_setup import configure_logging
from .paths import AppPaths
from .repository import ApplicationRepository
from .services import ApplicationService
from .styles import APP_STYLESHEET
from .ui.main_window import MainWindow


def run() -> int:
    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APPLICATION_NAME)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance()
    owns_application = app is None
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setStyleSheet(APP_STYLESHEET)

    database: Database | None = None
    try:
        paths = AppPaths.from_standard_paths()
        paths.ensure_directories()
        configure_logging(paths.log_path)
        database = Database(paths.database_path)
        database.initialize()
        service = ApplicationService(ApplicationRepository(database))
        backup_manager = BackupManager(database, paths)
        try:
            backup_manager.create_daily_backup()
        except BackupError as exc:
            logging.getLogger(__name__).warning("每日自动备份失败：%s", exc)
            QMessageBox.warning(
                None,
                "自动备份警告",
                f"程序可以继续使用，但今日自动备份失败：{exc}",
            )
        window = MainWindow(service, backup_manager, paths)
        window.show()
        app.aboutToQuit.connect(database.close)
        if owns_application:
            return app.exec()
        return 0
    except Exception as exc:
        logging.getLogger(__name__).exception("程序启动失败")
        QMessageBox.critical(None, "启动失败", f"{APP_DISPLAY_NAME}无法启动：{exc}")
        if database is not None:
            database.close()
        return 1
