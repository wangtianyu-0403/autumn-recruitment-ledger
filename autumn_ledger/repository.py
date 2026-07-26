from __future__ import annotations

import sqlite3
from datetime import datetime

from .constants import TIMESTAMP_FORMAT
from .database import Database
from .models import ApplicationRecord, StatusHistoryRecord


class RepositoryError(RuntimeError):
    """仓储操作失败。"""


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
                cursor = connection.execute(
                    f"""
                    INSERT INTO applications (
                        {", ".join(self._APPLICATION_COLUMNS)}, created_at, updated_at, is_deleted
                    ) VALUES ({placeholders}, ?, ?, 0)
                    """,
                    (*values, now, now),
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
    ) -> list[ApplicationRecord]:
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
            ORDER BY updated_at DESC, id DESC
        """
        try:
            rows = self.database.connection.execute(query, parameters).fetchall()
            return [ApplicationRecord.from_row(row) for row in rows]
        except sqlite3.Error as exc:
            raise RepositoryError(f"读取岗位列表失败:{exc}") from exc

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
    def _record_values(cls, record: ApplicationRecord) -> tuple[object, ...]:
        return tuple(getattr(record, column) for column in cls._APPLICATION_COLUMNS)

