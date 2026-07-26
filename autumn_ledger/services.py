from __future__ import annotations

from .constants import APPLICATION_STATUSES, INTERVIEW_STATUSES
from .models import ApplicationRecord, StatusHistoryRecord
from .repository import ApplicationRepository
from .validation import ValidationError, validate_application


class ApplicationService:
    def __init__(self, repository: ApplicationRepository) -> None:
        self.repository = repository

    def create(self, record: ApplicationRecord) -> int:
        return self.repository.create_application(validate_application(record))

    def update(self, record: ApplicationRecord) -> None:
        self.repository.update_application(validate_application(record))

    def update_status(self, application_id: int, new_status: str, notes: str = "") -> None:
        if new_status not in APPLICATION_STATUSES:
            raise ValidationError("请选择有效的投递状态。")
        self.repository.update_status(application_id, new_status, notes)

    def get(self, application_id: int) -> ApplicationRecord | None:
        return self.repository.get_application(application_id)

    def list(
        self,
        search_text: str = "",
        status: str | None = None,
    ) -> list[ApplicationRecord]:
        return self.repository.list_applications(search_text, status)

    def list_deleted(self) -> list[ApplicationRecord]:
        return self.repository.list_deleted()

    def history(self, application_id: int) -> list[StatusHistoryRecord]:
        return self.repository.list_status_history(application_id)

    def soft_delete(self, application_id: int) -> None:
        self.repository.soft_delete(application_id)

    def restore(self, application_id: int) -> None:
        self.repository.restore(application_id)

    def permanently_delete(self, application_id: int) -> None:
        self.repository.permanently_delete(application_id)

    def statistics(self) -> dict[str, int]:
        counts = self.repository.count_by_status()
        return {
            "全部岗位": sum(counts.values()),
            "已投递": counts.get("已投递", 0),
            "面试进行中": sum(counts.get(status, 0) for status in INTERVIEW_STATUSES),
            "已有Offer": counts.get("已有Offer", 0),
        }

