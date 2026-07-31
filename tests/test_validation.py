from __future__ import annotations

import pytest

from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.validation import ValidationError, normalize_url, validate_application


def valid_record() -> ApplicationRecord:
    return ApplicationRecord("示例公司", "研发工程师", "2026-07-26", "待投递")


@pytest.mark.parametrize(
    ("field", "message"),
    [("company_name", "公司名称"), ("position_name", "岗位名称")],
)
def test_required_text_fields(field: str, message: str) -> None:
    record = valid_record()
    setattr(record, field, "   ")
    with pytest.raises(ValidationError, match=message):
        validate_application(record)


def test_empty_url_is_valid() -> None:
    assert normalize_url("") == ""


def test_url_normalization_and_valid_http() -> None:
    assert normalize_url("example.com") == "https://example.com"
    assert (
        normalize_url("https://example.com/path")
        == "https://example.com/path"
    )


@pytest.mark.parametrize("url", ["ftp://example.com", "not-a-url", "http://bad host.com"])
def test_invalid_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        normalize_url(url)
