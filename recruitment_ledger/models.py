from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(slots=True)
class ApplicationRecord:
    company_name: str
    position_name: str
    application_date: str
    status: str
    job_description: str = ""
    company_url: str = ""
    recruitment_url: str = ""
    location: str = ""
    channel: str = ""
    salary: str = ""
    contact_name: str = ""
    contact_info: str = ""
    notes: str = ""
    follow_up_date: str | None = None
    id: int | None = None
    created_at: str = ""
    updated_at: str = ""
    is_deleted: bool = False
    is_pinned: bool = False
    manual_order: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ApplicationRecord":
        return cls(
            id=row["id"],
            company_name=row["company_name"],
            position_name=row["position_name"],
            job_description=row["job_description"],
            application_date=row["application_date"],
            status=row["status"],
            company_url=row["company_url"],
            recruitment_url=row["recruitment_url"],
            location=row["location"],
            channel=row["channel"],
            salary=row["salary"],
            contact_name=row["contact_name"],
            contact_info=row["contact_info"],
            notes=row["notes"],
            follow_up_date=row["follow_up_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_deleted=bool(row["is_deleted"]),
            is_pinned=bool(row["is_pinned"]),
            manual_order=int(row["manual_order"]),
        )


@dataclass(frozen=True, slots=True)
class StatusHistoryRecord:
    application_id: int
    new_status: str
    changed_at: str
    old_status: str | None = None
    notes: str = ""
    id: int | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "StatusHistoryRecord":
        return cls(
            id=row["id"],
            application_id=row["application_id"],
            old_status=row["old_status"],
            new_status=row["new_status"],
            changed_at=row["changed_at"],
            notes=row["notes"],
        )
