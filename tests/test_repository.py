from __future__ import annotations

import time

from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.repository import ApplicationRepository


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
