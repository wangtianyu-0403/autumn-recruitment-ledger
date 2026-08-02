from __future__ import annotations

from collections.abc import Sequence

import pytest

from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.repository import RepositoryError, SortMode
from recruitment_ledger.services import ApplicationService


class FakeRepository:
    def __init__(
        self,
        pinned_ids: Sequence[int] = (),
        unpinned_ids: Sequence[int] = (),
        *,
        automatic_ids: Sequence[int] | None = None,
    ) -> None:
        self.pinned_ids = list(pinned_ids)
        self.unpinned_ids = list(unpinned_ids)
        self.automatic_ids = (
            list(automatic_ids)
            if automatic_ids is not None
            else [*self.pinned_ids, *self.unpinned_ids]
        )
        self.saved_pinned: list[int] | None = None
        self.saved_unpinned: list[int] | None = None
        self.save_calls: list[tuple[list[int], bool]] = []
        self.batch_save_calls: list[
            tuple[list[int] | None, list[int] | None]
        ] = []
        self.list_arguments: tuple[str, str | None, bool, SortMode] | None = None
        self.pin_calls: list[tuple[int, bool]] = []

    def list_active_ids(self, sort_mode: SortMode) -> list[int]:
        if sort_mode is SortMode.MANUAL:
            return [*self.pinned_ids, *self.unpinned_ids]
        return list(self.automatic_ids)

    def get_application(self, application_id: int) -> ApplicationRecord | None:
        active_ids = {*self.pinned_ids, *self.unpinned_ids}
        if application_id not in active_ids:
            return None
        return ApplicationRecord(
            id=application_id,
            company_name=f"company-{application_id}",
            position_name="position",
            application_date="2026-07-30",
            status="待投递",
            is_pinned=application_id in self.pinned_ids,
        )

    def save_manual_order(
        self,
        application_ids: Sequence[int],
        pinned: bool,
    ) -> None:
        saved_ids = list(application_ids)
        self.save_calls.append((saved_ids, pinned))
        if pinned:
            self.pinned_ids = saved_ids
            self.saved_pinned = saved_ids
        else:
            self.unpinned_ids = saved_ids
            self.saved_unpinned = saved_ids

    def save_manual_orders(
        self,
        *,
        pinned_ids: Sequence[int] | None = None,
        unpinned_ids: Sequence[int] | None = None,
    ) -> None:
        saved_pinned = list(pinned_ids) if pinned_ids is not None else None
        saved_unpinned = list(unpinned_ids) if unpinned_ids is not None else None
        self.batch_save_calls.append((saved_pinned, saved_unpinned))
        if saved_pinned is not None:
            self.pinned_ids = saved_pinned
            self.saved_pinned = saved_pinned
        if saved_unpinned is not None:
            self.unpinned_ids = saved_unpinned
            self.saved_unpinned = saved_unpinned

    def list_applications(
        self,
        search_text: str = "",
        status: str | None = None,
        include_deleted: bool = False,
        sort_mode: SortMode = SortMode.UPDATED_AT,
    ) -> list[ApplicationRecord]:
        self.list_arguments = (search_text, status, include_deleted, sort_mode)
        return []

    def set_pinned(self, application_id: int, pinned: bool) -> None:
        self.pin_calls.append((application_id, pinned))


def test_reorder_visible_preserves_hidden_slots() -> None:
    repository = FakeRepository(unpinned_ids=[1, 2, 3, 4, 5])
    service = ApplicationService(repository)  # type: ignore[arg-type]

    service.reorder_visible([4, 2], SortMode.MANUAL)

    assert repository.saved_unpinned == [1, 4, 3, 2, 5]
    assert repository.batch_save_calls == [(None, [1, 4, 3, 2, 5])]


def test_reorder_visible_keeps_pin_groups_separate() -> None:
    repository = FakeRepository(pinned_ids=[1, 2], unpinned_ids=[3, 4])
    service = ApplicationService(repository)  # type: ignore[arg-type]

    service.reorder_visible([3, 2, 1, 4], SortMode.MANUAL)

    assert repository.saved_pinned == [2, 1]
    assert repository.saved_unpinned == [3, 4]
    assert repository.batch_save_calls == [([2, 1], [3, 4])]


@pytest.mark.parametrize(
    "visible_ids",
    ([None], [1, 1], [1, 999]),
    ids=["null", "duplicate", "inactive-or-unknown"],
)
def test_reorder_visible_rejects_invalid_ids_before_any_write(
    visible_ids: list[int | None],
) -> None:
    repository = FakeRepository(pinned_ids=[1], unpinned_ids=[2])
    service = ApplicationService(repository)  # type: ignore[arg-type]

    with pytest.raises(RepositoryError):
        service.reorder_visible(visible_ids, SortMode.MANUAL)  # type: ignore[arg-type]

    assert repository.save_calls == []
    assert repository.batch_save_calls == []


def test_automatic_reorder_uses_full_automatic_order_as_manual_baseline() -> None:
    repository = FakeRepository(
        pinned_ids=[1, 2],
        unpinned_ids=[3, 4, 5],
        automatic_ids=[2, 1, 5, 4, 3],
    )
    service = ApplicationService(repository)  # type: ignore[arg-type]

    service.reorder_visible([3, 5], SortMode.UPDATED_AT)

    assert repository.saved_pinned == [2, 1]
    assert repository.saved_unpinned == [3, 4, 5]
    assert repository.batch_save_calls == [([2, 1], [3, 4, 5])]


def test_list_passes_requested_sort_mode_to_repository() -> None:
    repository = FakeRepository()
    service = ApplicationService(repository)  # type: ignore[arg-type]

    service.list("python", "已投递", SortMode.APPLICATION_DATE)

    assert repository.list_arguments == (
        "python",
        "已投递",
        False,
        SortMode.APPLICATION_DATE,
    )


def test_set_pinned_delegates_to_repository() -> None:
    repository = FakeRepository(unpinned_ids=[7])
    service = ApplicationService(repository)  # type: ignore[arg-type]

    service.set_pinned(7, True)

    assert repository.pin_calls == [(7, True)]
