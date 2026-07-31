from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..constants import APPLICATION_CHANNELS, APPLICATION_STATUSES, DATE_FORMAT
from ..models import ApplicationRecord
from ..validation import ValidationError, validate_application


class ApplicationDialog(QDialog):
    def __init__(
        self,
        record: ApplicationRecord | None = None,
        parent: QWidget | None = None,
        save_callback: Callable[[ApplicationRecord], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_record = record
        self._save_callback = save_callback
        self.result_record: ApplicationRecord | None = None
        self.setWindowTitle("编辑岗位" if record else "新增公司/岗位")
        self.resize(690, 720)
        self.setMinimumSize(600, 580)
        self._build_ui()
        if record:
            self._populate(record)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self.company_edit = QLineEdit()
        self.company_edit.setObjectName("company_name")
        self.position_edit = QLineEdit()
        self.position_edit.setObjectName("position_name")
        self.application_date_edit = QDateEdit(QDate.currentDate())
        self.application_date_edit.setCalendarPopup(True)
        self.application_date_edit.setDisplayFormat(DATE_FORMAT)
        self.status_combo = QComboBox()
        self.status_combo.addItems(APPLICATION_STATUSES)
        self.jd_edit = QPlainTextEdit()
        self.jd_edit.setMaximumHeight(105)
        self.company_url_edit = QLineEdit()
        self.company_url_edit.setPlaceholderText("例如 example.com")
        self.recruitment_url_edit = QLineEdit()
        self.recruitment_url_edit.setPlaceholderText("例如 https://example.com/jobs/1")
        self.location_edit = QLineEdit()
        self.channel_combo = QComboBox()
        self.channel_combo.addItem("")
        self.channel_combo.addItems(APPLICATION_CHANNELS)
        self.salary_edit = QLineEdit()
        self.contact_name_edit = QLineEdit()
        self.contact_info_edit = QLineEdit()
        self.follow_up_enabled = QCheckBox("设置日期")
        self.follow_up_date_edit = QDateEdit(QDate.currentDate())
        self.follow_up_date_edit.setCalendarPopup(True)
        self.follow_up_date_edit.setDisplayFormat(DATE_FORMAT)
        self.follow_up_date_edit.setEnabled(False)
        self.follow_up_enabled.toggled.connect(self.follow_up_date_edit.setEnabled)
        follow_widget = QWidget()
        follow_layout = QHBoxLayout(follow_widget)
        follow_layout.setContentsMargins(0, 0, 0, 0)
        follow_layout.addWidget(self.follow_up_enabled)
        follow_layout.addWidget(self.follow_up_date_edit)
        follow_layout.addStretch(1)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMaximumHeight(105)

        required = QLabel("带 * 的项目为必填项")
        required.setStyleSheet("color: #667085;")
        form.addRow("", required)
        form.addRow("公司名称 *", self.company_edit)
        form.addRow("岗位名称 *", self.position_edit)
        form.addRow("投递日期 *", self.application_date_edit)
        form.addRow("当前进度 *", self.status_combo)
        form.addRow("岗位 JD", self.jd_edit)
        form.addRow("公司官网", self.company_url_edit)
        form.addRow("招聘页面", self.recruitment_url_edit)
        form.addRow("工作地点", self.location_edit)
        form.addRow("投递渠道", self.channel_combo)
        form.addRow("薪资范围", self.salary_edit)
        form.addRow("联系人", self.contact_name_edit)
        form.addRow("联系方式", self.contact_info_edit)
        form.addRow("下次跟进日期", follow_widget)
        form.addRow("备注", self.notes_edit)
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText("保存")
        save_button.setProperty("primary", True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    def _populate(self, record: ApplicationRecord) -> None:
        self.company_edit.setText(record.company_name)
        self.position_edit.setText(record.position_name)
        self.application_date_edit.setDate(
            QDate.fromString(record.application_date, DATE_FORMAT)
        )
        self.status_combo.setCurrentText(record.status)
        self.jd_edit.setPlainText(record.job_description)
        self.company_url_edit.setText(record.company_url)
        self.recruitment_url_edit.setText(record.recruitment_url)
        self.location_edit.setText(record.location)
        self.channel_combo.setCurrentText(record.channel)
        self.salary_edit.setText(record.salary)
        self.contact_name_edit.setText(record.contact_name)
        self.contact_info_edit.setText(record.contact_info)
        self.notes_edit.setPlainText(record.notes)
        if record.follow_up_date:
            self.follow_up_enabled.setChecked(True)
            self.follow_up_date_edit.setDate(
                QDate.fromString(record.follow_up_date, DATE_FORMAT)
            )

    def build_record(self) -> ApplicationRecord:
        source = self._source_record
        return ApplicationRecord(
            id=source.id if source else None,
            company_name=self.company_edit.text(),
            position_name=self.position_edit.text(),
            application_date=self.application_date_edit.date().toString(DATE_FORMAT),
            status=self.status_combo.currentText(),
            job_description=self.jd_edit.toPlainText(),
            company_url=self.company_url_edit.text(),
            recruitment_url=self.recruitment_url_edit.text(),
            location=self.location_edit.text(),
            channel=self.channel_combo.currentText(),
            salary=self.salary_edit.text(),
            contact_name=self.contact_name_edit.text(),
            contact_info=self.contact_info_edit.text(),
            follow_up_date=(
                self.follow_up_date_edit.date().toString(DATE_FORMAT)
                if self.follow_up_enabled.isChecked()
                else None
            ),
            notes=self.notes_edit.toPlainText(),
            created_at=source.created_at if source else "",
            updated_at=source.updated_at if source else "",
            is_deleted=source.is_deleted if source else False,
        )

    def _save(self) -> None:
        try:
            self.result_record = validate_application(self.build_record())
            if self._save_callback is not None:
                self._save_callback(self.result_record)
        except ValidationError as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"无法保存岗位信息：{exc}")
            return
        self.accept()
