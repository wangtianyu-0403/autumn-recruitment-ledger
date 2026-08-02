from __future__ import annotations

import sqlite3
from datetime import datetime
from enum import Enum
from typing import Sequence

from .constants import TIMESTAMP_FORMAT
from .database import Database
from .models import ApplicationRecord, StatusHistoryRecord


class RepositoryError(RuntimeError):
    """仓储操作失败。"""


class SortMode(str, Enum):
    MANUAL = "manual"
    APPLICATION_DATE = "application_date"
    UPDATED_AT = "updated_at"


_ORDER_BY = {
    SortMode.MANUAL: "is_pinned DESC, manual_order ASC, id ASC",
    SortMode.APPLICATION_DATE: (
        "is_pinned DESC, application_date DESC, manual_order ASC, id DESC"
    ),
    SortMode.UPDATED_AT: (
        "is_pinned DESC, updated_at DESC, manual_order ASC, id DESC"
    ),
}


def current_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


class ApplicationRepository:
    _APPLICATION_COLUMNS = (
        "company_name",
        "position_name",
        "job_description",
        "application_date",
        "status",
        "company_url",
        "recruitment_url",
        "location",
        "channel",
        "salary",
        "contact_name",
        "contact_info",
        "notes",
        "follow_up_date",
    )

    def __init__(self, database: Database) -> None:
        self.database = database

    def create_application(self, record: ApplicationRecord) -> int:
        now = current_timestamp()
        values = self._record_values(record)
        placeholders = ", ".join("?" for _ in self._APPLICATION_COLUMNS)
        try:
            with self.database.transaction() as connection:
                minimum_order = connection.execute(
                    """
                    SELECT MIN(manual_order)
                    FROM applications
                    WHERE is_deleted = 0 AND is_pinned = 0
                    """
                ).fetchone()[0]
                manual_order = 0 if minimum_order is None else int(minimum_order) - 1
                cursor = connection.execute(
                    f"""
                    INSERT INTO applications (
                        {", ".join(self._APPLICATION_COLUMNS)}, created_at, updated_at,
                        is_deleted, is_pinned, manual_order
                    ) VALUES ({placeholders}, ?, ?, 0, 0, ?)
                    """,
                    (*values, now, now, manual_order),
                )
                application_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    INSERT INTO status_history (
                        application_id, old_status, new_status, changed_at, notes
                    ) VALUES (?, NULL, ?, ?, ?)
                    """,
                    (application_id, record.status, now, "创建岗位"),
                )
            return application_id
        except sqlite3.Error as exc:
            raise RepositoryError(f"新增岗位失败:{exc}") from exc

    def get_application(self, application_id: int) -> ApplicationRecord | None:
        try:
            row = self.database.connection.execute(
                "SELECT * FROM applications WHERE id = ?",
                (application_id,),
            ).fetchone()
            return ApplicationRecord.from_row(row) if row else None
        except sqlite3.Error as exc:
            raise RepositoryError(f"读取岗位失败:{exc}") from exc

    def list_applications(
        self,
        search_text: str = "",
        status: str | None = None,
        include_deleted: bool = False,
        sort_mode: SortMode = SortMode.UPDATED_AT,
    ) -> list[ApplicationRecord]:
        order_by = self._order_by(sort_mode)
        clauses = ["1 = 1"] if include_deleted else ["is_deleted = 0"]
        parameters: list[object] = []
        cleaned_search = search_text.strip()
        if cleaned_search:
            pattern = f"%{cleaned_search}%"
            clauses.append(
                """
                (
                    company_name LIKE ? COLLATE NOCASE OR
                    position_name LIKE ? COLLATE NOCASE OR
                    location LIKE ? COLLATE NOCASE OR
                    notes LIKE ? COLLATE NOCASE
                )
                """
            )
            parameters.extend([pattern, pattern, pattern, pattern])
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        query = f"""
            SELECT * FROM applications
            WHERE {" AND ".join(clauses)}
            ORDER BY {order_by}
        """
        try:
            rows = self.database.connection.execute(query, parameters).fetchall()
            return [ApplicationRecord.from_row(row) for row in rows]
        except sqlite3.Error as exc:
            raise RepositoryError(f"读取岗位列表失败:{exc}") from exc

    def list_active_ids(self, sort_mode: SortMode) -> list[int]:
        order_by = self._order_by(sort_mode)
        try:
            rows = self.database.connection.execute(
                f"""
                SELECT id FROM applications
                WHERE is_deleted = 0
                ORDER BY {order_by}
                """
            ).fetchall()
            return [int(row["id"]) for row in rows]
        except sqlite3.Error as exc:
            raise RepositoryError(f"读取岗位顺序失败：{exc}") from exc

    def set_pinned(self, application_id: int, pinned: bool) -> None:
        target = int(bool(pinned))
        try:
            with self.database.transaction() as connection:
                row = connection.execute(
                    """
                    SELECT is_pinned FROM applications
                    WHERE id = ? AND is_deleted = 0
                    """,
                    (application_id,),
                ).fetchone()
                if row is None:
                    raise RepositoryError("岗位不存在或已被删除。")
                if int(row["is_pinned"]) == target:
                    return
                minimum_order = connection.execute(
                    """
                    SELECT MIN(manual_order) FROM applications
                    WHERE is_deleted = 0 AND is_pinned = ? AND id != ?
                    """,
                    (target, application_id),
                ).fetchone()[0]
                manual_order = 0 if minimum_order is None else int(minimum_order) - 1
                connection.execute(
                    """
                    UPDATE applications
                    SET is_pinned = ?, manual_order = ?
                    WHERE id = ? AND is_deleted = 0
                    """,
                    (target, manual_order, application_id),
                )
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            raise RepositoryError(f"修改置顶状态失败：{exc}") from exc

    def save_manual_order(
        self,
        application_ids: Sequence[int],
        pinned: bool,
    ) -> None:
        if pinned:
            self.save_manual_orders(pinned_ids=application_ids)
        else:
            self.save_manual_orders(unpinned_ids=application_ids)

    def save_manual_orders(
        self,
        *,
        pinned_ids: Sequence[int] | None = None,
        unpinned_ids: Sequence[int] | None = None,
    ) -> None:
        submitted_groups: list[tuple[int, list[int]]] = []
        if pinned_ids is not None:
            submitted_groups.append((1, list(pinned_ids)))
        if unpinned_ids is not None:
            submitted_groups.append((0, list(unpinned_ids)))

        try:
            with self.database.transaction() as connection:
                for target, supplied_ids in submitted_groups:
                    if len(supplied_ids) != len(set(supplied_ids)):
                        raise RepositoryError("岗位顺序包含重复记录。")
                    rows = connection.execute(
                        """
                        SELECT id FROM applications
                        WHERE is_deleted = 0 AND is_pinned = ?
                        """,
                        (target,),
                    ).fetchall()
                    active_ids = {int(row["id"]) for row in rows}
                    if set(supplied_ids) != active_ids:
                        raise RepositoryError(
                            "岗位顺序必须完整且属于同一置顶分组。"
                        )

                for _target, supplied_ids in submitted_groups:
                    connection.executemany(
                        "UPDATE applications SET manual_order = ? WHERE id = ?",
                        (
                            (index, application_id)
                            for index, application_id in enumerate(supplied_ids)
                        ),
                    )
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            raise RepositoryError(f"保存岗位顺序失败：{exc}") from exc

    def list_deleted(self) -> list[ApplicationRecord]:
        try:
            rows = self.database.connection.execute(
                """
                SELECT * FROM applications
                WHERE is_deleted = 1
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
            return [ApplicationRecord.from_row(row) for row in rows]
        except sqlite3.Error as exc:
            raise RepositoryError(f"读取回收站失败:{exc}") from exc

    def update_application(self, record: ApplicationRecord) -> None:
        if record.id is None:
            raise RepositoryError("更新岗位时缺少记录ID。")
        now = current_timestamp()
        assignments = ", ".join(f"{column} = ?" for column in self._APPLICATION_COLUMNS)
        try:
            with self.database.transaction() as connection:
                current = connection.execute(
                    "SELECT status FROM applications WHERE id = ? AND is_deleted = 0",
                    (record.id,),
                ).fetchone()
                if current is None:
                    raise RepositoryError("岗位不存在或已被删除。")
                connection.execute(
                    f"UPDATE applications SET {assignments}, updated_at = ? WHERE id = ?",
                    (*self._record_values(record), now, record.id),
                )
                if current["status"] != record.status:
                    connection.execute(
                        """
                        INSERT INTO status_history (
                            application_id, old_status, new_status, changed_at, notes
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (record.id, current["status"], record.status, now, record.notes),
                    )
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            raise RepositoryError(f"更新岗位失败:{exc}") from exc

    def update_status(self, application_id: int, new_status: str, notes: str = "") -> None:
        now = current_timestamp()
        try:
            with self.database.transaction() as connection:
                row = connection.execute(
                    "SELECT status FROM applications WHERE id = ? AND is_deleted = 0",
                    (application_id,),
                ).fetchone()
                if row is None:
                    raise RepositoryError("岗位不存在或已被删除。")
                old_status = str(row["status"])
                if old_status == new_status:
                    return
                connection.execute(
                    "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                    (new_status, now, application_id),
                )
                connection.execute(
                    """
                    INSERT INTO status_history (
                        application_id, old_status, new_status, changed_at, notes
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (application_id, old_status, new_status, now, notes.strip()),
                )
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            raise RepositoryError(f"修改状态失败:{exc}") from exc

    def soft_delete(self, application_id: int) -> None:
        self._set_deleted(application_id, True)

    def restore(self, application_id: int) -> None:
        self._set_deleted(application_id, False)

    def permanently_delete(self, application_id: int) -> None:
        try:
            with self.database.transaction() as connection:
                cursor = connection.execute(
                    "DELETE FROM applications WHERE id = ? AND is_deleted = 1",
                    (application_id,),
                )
                if cursor.rowcount == 0:
                    raise RepositoryError("回收站中未找到该岗位。")
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            raise RepositoryError(f"永久删除失败:{exc}") from exc

    def list_status_history(self, application_id: int) -> list[StatusHistoryRecord]:
        try:
            rows = self.database.connection.execute(
                """
                SELECT * FROM status_history
                WHERE application_id = ?
                ORDER BY changed_at ASC, id ASC
                """,
                (application_id,),
            ).fetchall()
            return [StatusHistoryRecord.from_row(row) for row in rows]
        except sqlite3.Error as exc:
            raise RepositoryError(f"读取状态历史失败:{exc}") from exc

    def count_by_status(self) -> dict[str, int]:
        try:
            rows = self.database.connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM applications
                WHERE is_deleted = 0
                GROUP BY status
                """
            ).fetchall()
            return {str(row["status"]): int(row["count"]) for row in rows}
        except sqlite3.Error as exc:
            raise RepositoryError(f"统计岗位失败:{exc}") from exc

    def _set_deleted(self, application_id: int, deleted: bool) -> None:
        now = current_timestamp()
        expected = 0 if deleted else 1
        try:
            with self.database.transaction() as connection:
                cursor = connection.execute(
                    """
                    UPDATE applications
                    SET is_deleted = ?, updated_at = ?
                    WHERE id = ? AND is_deleted = ?
                    """,
                    (int(deleted), now, application_id, expected),
                )
                if cursor.rowcount == 0:
                    raise RepositoryError("岗位不存在或状态已发生变化。")
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            action = "删除" if deleted else "恢复"
            raise RepositoryError(f"{action}岗位失败:{exc}") from exc

    @classmethod
    def _order_by(cls, sort_mode: SortMode) -> str:
        try:
            normalized = SortMode(sort_mode)
        except (TypeError, ValueError) as exc:
            raise RepositoryError("未知排序模式。") from exc
        return _ORDER_BY[normalized]

    @classmethod
    def _record_values(cls, record: ApplicationRecord) -> tuple[object, ...]:
        return tuple(getattr(record, column) for column in cls._APPLICATION_COLUMNS)
