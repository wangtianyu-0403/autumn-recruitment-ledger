from __future__ import annotations

import json
from pathlib import Path

import pytest

from autumn_ledger.update import (
    ReleaseInfo,
    UpdateError,
    fetch_latest_release,
    parse_version,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("v1.2.3", (1, 2, 3)),
        ("1.2.3", (1, 2, 3)),
        ("v0.0.0", (0, 0, 0)),
    ],
)
def test_parse_version_accepts_semantic_versions(
    value: str,
    expected: tuple[int, int, int],
) -> None:
    assert parse_version(value) == expected


@pytest.mark.parametrize("value", ["", "v1", "v1.2", "v1.2.3.4", "v1.x.3", "v-1.2.3"])
def test_parse_version_rejects_invalid_values(value: str) -> None:
    with pytest.raises(UpdateError, match="版本"):
        parse_version(value)


def _write_release(tmp_path: Path, payload: dict[str, object]) -> str:
    path = tmp_path / "release.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path.as_uri()


def _valid_payload() -> dict[str, object]:
    return {
        "draft": False,
        "prerelease": False,
        "tag_name": "v1.2.0",
        "html_url": "https://github.com/example/releases/tag/v1.2.0",
        "assets": [
            {
                "name": "autumn-recruitment-ledger-Windows-x64.zip",
                "browser_download_url": "https://example.invalid/app.zip",
                "digest": "sha256:" + "a" * 64,
            }
        ],
    }


def test_fetch_latest_release_parses_valid_file_response(tmp_path: Path) -> None:
    release = fetch_latest_release(_write_release(tmp_path, _valid_payload()))

    assert release == ReleaseInfo(
        version=(1, 2, 0),
        tag_name="v1.2.0",
        asset_url="https://example.invalid/app.zip",
        asset_digest="sha256:" + "a" * 64,
        html_url="https://github.com/example/releases/tag/v1.2.0",
    )


@pytest.mark.parametrize(("field", "value"), [("draft", True), ("prerelease", True)])
def test_fetch_latest_release_rejects_unstable_releases(
    tmp_path: Path,
    field: str,
    value: bool,
) -> None:
    payload = _valid_payload()
    payload[field] = value

    with pytest.raises(UpdateError, match="正式"):
        fetch_latest_release(_write_release(tmp_path, payload))


def test_fetch_latest_release_requires_named_asset(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["assets"] = []

    with pytest.raises(UpdateError, match="更新包"):
        fetch_latest_release(_write_release(tmp_path, payload))


def test_fetch_latest_release_requires_sha256_digest(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["assets"][0]["digest"] = None  # type: ignore[index]

    with pytest.raises(UpdateError, match="SHA-256"):
        fetch_latest_release(_write_release(tmp_path, payload))
