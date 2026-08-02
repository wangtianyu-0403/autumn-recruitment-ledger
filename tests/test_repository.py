from __future__ import annotations

import time

import pytest

from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.repository import (
    ApplicationRepository,
    RepositoryError,
    SortMode,
)


def make_record(
    company: str = "星河科技",
    position: str = "Python工程师",
    status: str = "已投递",
) -> ApplicationRecord:
    return ApplicationRecord(
        company_name=company,
        position_name=position,
        application_date="2026-07-26",
        status=status,
        location="上海",
        notes="校招重点岗位",
        channel="校园招聘",
    )


def test_create_read_and_initial_history(repository: ApplicationRepository) -> None:
    application_id = repository.create_application(make_record())
    loaded = repository.get_application(application_id)
    history = repository.list_status_history(application_id)
    assert loaded is not None
    assert loaded.position_name == "Python工程师"
    assert len(history) == 1
    assert history[0].old_status is None
    assert history[0].new_status == "已投递"


def test_loaded_application_has_default_ordering_fields(
    repository: ApplicationRepository,
) -> None:
    application_id = repository.create_application(make_record())

    loaded = repository.get_application(application_id)

    assert loaded is not None
    assert loaded.is_pinned is False
    assert loaded.manual_order == 0


def test_update_information_and_status_history(repository: ApplicationRepository) -> None:
    application_id = repository.create_application(make_record())
    loaded = repository.get_application(application_id)
    assert loaded is not None
    loaded.position_name = "高级Python工程师"
    loaded.status = "笔试"
    repository.update_application(loaded)

    updated = repository.get_application(application_id)
    history = repository.list_status_history(application_id)
    assert updated is not None
    assert updated.position_name == "高级Python工程师"
    assert updated.status == "笔试"
    assert len(history) == 2
    assert history[-1].old_status == "已投递"


def test_unchanged_status_does_not_duplicate_history(
    repository: ApplicationRepository,
) -> None:
    application_id = repository.create_application(make_record())
    repository.update_status(application_id, "已投递")
    loaded = repository.get_application(application_id)
    assert loaded is not None
    loaded.location = "杭州"
    repository.update_application(loaded)
    assert len(repository.list_status_history(application_id)) == 1


def test_search_and_status_filter(repository: ApplicationRepository) -> None:
    repository.create_application(make_record("晨光网络", "后端开发", "已投递"))
    repository.create_application(make_record("远山智能", "控制算法", "笔试"))
    assert [item.company_name for item in repository.list_applications("晨光")] == [
        "晨光网络"
    ]
    assert [item.position_name for item in repository.list_applications("控制算法")] == [
        "控制算法"
    ]
    assert [item.status for item in repository.list_applications(status="笔试")] == [
        "笔试"
    ]


def test_soft_delete_restore_and_permanent_delete(
    repository: ApplicationRepository,
) -> None:
    application_id = repository.create_application(make_record())
    repository.soft_delete(application_id)
    assert repository.list_applications() == []
    assert [item.id for item in repository.list_deleted()] == [application_id]

    repository.restore(application_id)
    assert repository.get_application(application_id) is not None
    assert len(repository.list_applications()) == 1

    repository.soft_delete(application_id)
    repository.permanently_delete(application_id)
    assert repository.get_application(application_id) is None
    assert repository.list_status_history(application_id) == []


def test_statistics_and_updated_order(repository: ApplicationRepository) -> None:
    first = repository.create_application(make_record("甲公司", "岗位甲", "已投递"))
    second = repository.create_application(make_record("乙公司", "岗位乙", "已有Offer"))
    time.sleep(1.05)
    repository.update_status(first, "笔试")

    counts = repository.count_by_status()
    listed = repository.list_applications()
    assert counts == {"笔试": 1, "已有Offer": 1}
    assert [item.id for item in listed] == [first, second]


def create_ordered_record(
    repository: ApplicationRepository,
    company: str,
    application_date: str,
) -> int:
    record = make_record(company=company)
    record.application_date = application_date
    return repository.create_application(record)


def test_list_applications_supports_all_stable_sort_modes(
    repository: ApplicationRepository,
) -> None:
    first = create_ordered_record(repository, "first", "2026-01-01")
    second = create_ordered_record(repository, "second", "2026-07-30")
    third = create_ordered_record(repository, "third", "2026-07-30")
    connection = repository.database.connection
    connection.execute(
        "UPDATE applications SET updated_at = '2026-01-01 00:00:00' WHERE id = ?",
        (first,),
    )
    connection.execute(
        "UPDATE applications SET updated_at = '2026-07-30 00:00:00' WHERE id IN (?, ?)",
        (second, third),
    )
    connection.commit()

    assert [
        item.id
        for item in repository.list_applications(sort_mode=SortMode.MANUAL)
    ] == [third, second, first]
    assert [
        item.id
        for item in repository.list_applications(sort_mode=SortMode.APPLICATION_DATE)
    ] == [third, second, first]
    assert [
        item.id
        for item in repository.list_applications(sort_mode=SortMode.UPDATED_AT)
    ] == [third, second, first]


def test_pinned_records_precede_automatic_sort_and_keep_updated_timestamp(
    repository: ApplicationRepository,
) -> None:
    older = create_ordered_record(repository, "older", "2026-01-01")
    newer = create_ordered_record(repository, "newer", "2026-07-30")
    before = repository.get_application(older)
    assert before is not None

    repository.set_pinned(older, True)

    after = repository.get_application(older)
    assert after is not None
    assert after.updated_at == before.updated_at
    assert [
        item.id
        for item in repository.list_applications(sort_mode=SortMode.APPLICATION_DATE)
    ] == [older, newer]
    assert [
        item.id
        for item in repository.list_applications(sort_mode=SortMode.UPDATED_AT)
    ][0] == older


def test_set_pinned_moves_record_to_top_of_destination_group(
    repository: ApplicationRepository,
) -> None:
    first = create_ordered_record(repository, "first", "2026-01-01")
    second = create_ordered_record(repository, "second", "2026-01-02")
    repository.set_pinned(first, True)
    repository.set_pinned(second, True)

    assert repository.list_active_ids(SortMode.MANUAL) == [second, first]

    repository.set_pinned(second, False)

    assert repository.list_active_ids(SortMode.MANUAL) == [first, second]


def test_new_record_enters_top_of_unpinned_manual_group(
    repository: ApplicationRepository,
) -> None:
    first = create_ordered_record(repository, "first", "2026-01-01")
    second = create_ordered_record(repository, "second", "2026-01-02")

    assert repository.list_active_ids(SortMode.MANUAL) == [second, first]


@pytest.mark.parametrize(
    "supplied_ids",
    [
        lambda first, second, pinned: [first, first],
        lambda first, second, pinned: [first, 999999],
        lambda first, second, pinned: [first, pinned],
        lambda first, second, pinned: [first],
    ],
    ids=["duplicate", "invalid", "cross-group", "incomplete"],
)
def test_save_manual_order_rejects_invalid_sets_without_partial_writes(
    repository: ApplicationRepository,
    supplied_ids,
) -> None:
    first = create_ordered_record(repository, "first", "2026-01-01")
    second = create_ordered_record(repository, "second", "2026-01-02")
    pinned = create_ordered_record(repository, "pinned", "2026-01-03")
    repository.set_pinned(pinned, True)
    before = {
        row["id"]: row["manual_order"]
        for row in repository.database.connection.execute(
            "SELECT id, manual_order FROM applications ORDER BY id"
        )
    }

    with pytest.raises(RepositoryError):
        repository.save_manual_order(
            supplied_ids(first, second, pinned),
            pinned=False,
        )

    after = {
        row["id"]: row["manual_order"]
        for row in repository.database.connection.execute(
            "SELECT id, manual_order FROM applications ORDER BY id"
        )
    }
    assert after == before


def test_save_manual_order_persists_complete_group_atomically(
    repository: ApplicationRepository,
) -> None:
    first = create_ordered_record(repository, "first", "2026-01-01")
    second = create_ordered_record(repository, "second", "2026-01-02")

    repository.save_manual_order([first, second], pinned=False)

    assert repository.list_active_ids(SortMode.MANUAL) == [first, second]


def test_save_manual_orders_rolls_back_both_groups_when_second_update_fails(
    repository: ApplicationRepository,
) -> None:
    first = create_ordered_record(repository, "first", "2026-01-01")
    second = create_ordered_record(repository, "second", "2026-01-02")
    third = create_ordered_record(repository, "third", "2026-01-03")
    fourth = create_ordered_record(repository, "fourth", "2026-01-04")
    repository.set_pinned(third, True)
    repository.set_pinned(fourth, True)
    connection = repository.database.connection
    before = {
        int(row["id"]): int(row["manual_order"])
        for row in connection.execute(
            "SELECT id, manual_order FROM applications ORDER BY id"
        )
    }
    connection.execute(
        """
        CREATE TRIGGER fail_unpinned_manual_order
        BEFORE UPDATE OF manual_order ON applications
        WHEN OLD.is_pinned = 0
        BEGIN
            SELECT RAISE(ABORT, 'injected second-group failure');
        END
        """
    )
    connection.commit()

    with pytest.raises(RepositoryError, match="保存岗位顺序失败"):
        repository.save_manual_orders(
            pinned_ids=[third, fourth],
            unpinned_ids=[first, second],
        )

    after = {
        int(row["id"]): int(row["manual_order"])
        for row in connection.execute(
            "SELECT id, manual_order FROM applications ORDER BY id"
        )
    }
    assert after == before


def test_invalid_sort_mode_is_rejected(repository: ApplicationRepository) -> None:
    with pytest.raises(RepositoryError, match="未知排序模式"):
        repository.list_applications(sort_mode="updated_at; DROP TABLE applications")


def test_soft_delete_and_restore_preserve_ordering_fields(
    repository: ApplicationRepository,
) -> None:
    application_id = create_ordered_record(repository, "ordered", "2026-01-01")
    repository.set_pinned(application_id, True)
    before = repository.get_application(application_id)
    assert before is not None

    repository.soft_delete(application_id)
    deleted = repository.get_application(application_id)
    assert deleted is not None
    assert (deleted.is_pinned, deleted.manual_order) == (
        before.is_pinned,
        before.manual_order,
    )

    repository.restore(application_id)
    restored = repository.get_application(application_id)
    assert restored is not None
    assert (restored.is_pinned, restored.manual_order) == (
        before.is_pinned,
        before.manual_order,
    )
