from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from .constants import APPLICATION_STATUSES, ISO_DATE_FORMAT
from .models import ApplicationRecord


class ValidationError(ValueError):
    """用户输入校验错误。"""


def normalize_url(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    candidate = cleaned if "://" in cleaned else f"https://{cleaned}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValidationError("网址只支持 http 或 https。")
    if not parsed.netloc or "." not in parsed.netloc:
        raise ValidationError("请输入有效的网址,例如 https://example.com。")
    if any(character.isspace() for character in parsed.netloc):
        raise ValidationError("网址中不能包含空格。")
    return candidate


def validate_iso_date(value: str, field_name: str, optional: bool = False) -> str | None:
    cleaned = value.strip()
    if not cleaned and optional:
        return None
    if not cleaned:
        raise ValidationError(f"{field_name}不能为空。")
    try:
        datetime.strptime(cleaned, ISO_DATE_FORMAT)
    except ValueError as exc:
        raise ValidationError(f"{field_name}必须使用 YYYY-MM-DD 格式。") from exc
    return cleaned


def validate_application(record: ApplicationRecord) -> ApplicationRecord:
    company_name = record.company_name.strip()
    position_name = record.position_name.strip()
    if not company_name:
        raise ValidationError("公司名称不能为空。")
    if not position_name:
        raise ValidationError("岗位名称不能为空。")
    if record.status not in APPLICATION_STATUSES:
        raise ValidationError("请选择有效的投递状态。")
    application_date = validate_iso_date(record.application_date, "投递日期")
    follow_up_date = (
        validate_iso_date(record.follow_up_date, "下次跟进日期", optional=True)
        if record.follow_up_date
        else None
    )
    return ApplicationRecord(
        id=record.id,
        company_name=company_name,
        position_name=position_name,
        job_description=record.job_description.strip(),
        application_date=str(application_date),
        status=record.status,
        company_url=normalize_url(record.company_url),
        recruitment_url=normalize_url(record.recruitment_url),
        location=record.location.strip(),
        channel=record.channel.strip(),
        salary=record.salary.strip(),
        contact_name=record.contact_name.strip(),
        contact_info=record.contact_info.strip(),
        notes=record.notes.strip(),
        follow_up_date=follow_up_date,
        created_at=record.created_at,
        updated_at=record.updated_at,
        is_deleted=record.is_deleted,
    )

