from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .models import ApplicationRecord


class ExportError(RuntimeError):
    """CSV导出错误。"""


class EmptyExportError(ExportError):
    """没有可导出的记录。"""


CSV_HEADERS: tuple[tuple[str, str], ...] = (
    ("公司名称", "company_name"),
    ("岗位名称", "position_name"),
    ("岗位JD", "job_description"),
    ("投递日期", "application_date"),
    ("当前进度", "status"),
    ("公司官网", "company_url"),
    ("招聘页面", "recruitment_url"),
    ("工作地点", "location"),
    ("投递渠道", "channel"),
    ("薪资范围", "salary"),
    ("联系人", "contact_name"),
    ("联系方式", "contact_info"),
    ("下次跟进日期", "follow_up_date"),
    ("备注", "notes"),
    ("创建时间", "created_at"),
    ("最后更新", "updated_at"),
)


def default_export_filename(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return f"秋招台账_{current:%Y%m%d_%H%M%S}.csv"


def export_applications_to_csv(
    records: Sequence[ApplicationRecord],
    destination: Path,
) -> Path:
    if not records:
        raise EmptyExportError("当前筛选条件下没有可导出的岗位。")
    target = destination.expanduser().resolve()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([header for header, _ in CSV_HEADERS])
            for record in records:
                writer.writerow(
                    [
                        "" if getattr(record, field) is None else getattr(record, field)
                        for _, field in CSV_HEADERS
                    ]
                )
        return target
    except OSError as exc:
        raise ExportError(f"无法写入CSV文件:{exc}") from exc

