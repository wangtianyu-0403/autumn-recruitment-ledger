from __future__ import annotations

from collections.abc import Sequence

from .constants import APPLICATION_STATUSES, INTERVIEW_STATUSES
from .models import ApplicationRecord, StatusHistoryRecord
from .repository import ApplicationRepository, RepositoryError, SortMode
from .validation import ValidationError, validate_application


def _merge_visible_order(
    full_ids: Sequence[int],
    visible_ids: Sequence[int],
) -> list[int]:
    visible_set = set(visible_ids)
    iterator = iter(visible_ids)
    return [next(iterator) if value in visible_set else value for value in full_ids]


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
        sort_mode: SortMode = SortMode.UPDATED_AT,
    ) -> list[ApplicationRecord]:
        return self.repository.list_applications(
            search_text,
            status,
            sort_mode=sort_mode,
        )

    def set_pinned(self, application_id: int, pinned: bool) -> None:
        self.repository.set_pinned(application_id, pinned)

    def reorder_visible(
        self,
        visible_ids: Sequence[int],
        sort_mode: SortMode,
    ) -> None:
        requested_ids = list(visible_ids)
        if any(application_id is None for application_id in requested_ids):
            raise RepositoryError("岗位顺序不能包含空记录。")
        if len(requested_ids) != len(set(requested_ids)):
            raise RepositoryError("岗位顺序包含重复记录。")

        try:
            resolved_mode = SortMode(sort_mode)
        except (TypeError, ValueError) as exc:
            raise RepositoryError("未知排序模式。") from exc

        full_ids = self.repository.list_active_ids(resolved_mode)
        if not set(requested_ids).issubset(full_ids):
            raise RepositoryError("岗位顺序包含不存在或已删除的记录。")

        pinned_by_id: dict[int, bool] = {}
        for application_id in full_ids:
            record = self.repository.get_application(application_id)
            if record is None or record.is_deleted:
                raise RepositoryError("岗位顺序包含不存在或已删除的记录。")
            pinned_by_id[application_id] = record.is_pinned

        pinned_ids = [
            application_id
            for application_id in full_ids
            if pinned_by_id[application_id]
        ]
        unpinned_ids = [
            application_id
            for application_id in full_ids
            if not pinned_by_id[application_id]
        ]
        visible_pinned = [
            application_id
            for application_id in requested_ids
            if pinned_by_id[application_id]
        ]
        visible_unpinned = [
            application_id
            for application_id in requested_ids
            if not pinned_by_id[application_id]
        ]

        final_pinned = _merge_visible_order(pinned_ids, visible_pinned)
        final_unpinned = _merge_visible_order(unpinned_ids, visible_unpinned)
        if resolved_mode is not SortMode.MANUAL or visible_pinned:
            self.repository.save_manual_order(final_pinned, pinned=True)
        if resolved_mode is not SortMode.MANUAL or visible_unpinned:
            self.repository.save_manual_order(final_unpinned, pinned=False)

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
