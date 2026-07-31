from __future__ import annotations

import csv
from pathlib import Path

import pytest

from recruitment_ledger.export import EmptyExportError, export_applications_to_csv
from recruitment_ledger.models import ApplicationRecord


def test_export_chinese_and_special_characters(tmp_path: Path) -> None:
    record = ApplicationRecord(
        "中文,公司",
        '研发"工程师',
        "2026-07-26",
        "已投递",
        job_description="第一行\n第二行",
        notes='包含,逗号和"引号"',
    )
    destination = tmp_path / "export.csv"
    export_applications_to_csv([record], destination)
    raw = destination.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    with destination.open(encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    assert rows[1][0] == "中文,公司"
    assert rows[1][1] == '研发"工程师'
    assert rows[1][2] == "第一行\n第二行"


def test_empty_export_does_not_create_file(tmp_path: Path) -> None:
    destination = tmp_path / "empty.csv"
    with pytest.raises(EmptyExportError):
        export_applications_to_csv([], destination)
    assert not destination.exists()
