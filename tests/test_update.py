from __future__ import annotations

import json
import subprocess
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest

from autumn_ledger.update import (
    ReleaseInfo,
    UpdateError,
    download_release_asset,
    fetch_latest_release,
    parse_version,
    validate_update_archive,
    write_updater_script,
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


def _release_for_file(path: Path, digest: str | None = None) -> ReleaseInfo:
    actual_digest = digest or f"sha256:{sha256(path.read_bytes()).hexdigest()}"
    return ReleaseInfo(
        version=(1, 1, 0),
        tag_name="v1.1.0",
        asset_url=path.as_uri(),
        asset_digest=actual_digest,
        html_url="https://github.com/example/releases/tag/v1.1.0",
    )


def test_download_release_asset_verifies_digest_and_reports_progress(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.zip"
    source.write_bytes(b"verified update bytes")
    destination = tmp_path / "download" / "update.zip"
    progress: list[tuple[int, int]] = []

    result = download_release_asset(
        _release_for_file(source),
        destination,
        lambda downloaded, total: progress.append((downloaded, total)),
    )

    assert result == destination
    assert destination.read_bytes() == b"verified update bytes"
    assert progress[-1][0] == len(b"verified update bytes")


def test_download_release_asset_rejects_wrong_digest(tmp_path: Path) -> None:
    source = tmp_path / "source.zip"
    source.write_bytes(b"tampered")
    destination = tmp_path / "update.zip"

    with pytest.raises(UpdateError, match="SHA-256"):
        download_release_asset(
            _release_for_file(source, "sha256:" + "0" * 64),
            destination,
        )

    assert not destination.exists()


def _write_update_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def _valid_update_members() -> dict[str, bytes]:
    return {
        "秋招进程台账/秋招进程台账.exe": b"new-exe",
        "秋招进程台账/_internal/python314.dll": b"new-runtime",
        "秋招进程台账/version.txt": b"new-version",
    }


def test_validate_update_archive_accepts_complete_package(tmp_path: Path) -> None:
    archive = _write_update_zip(tmp_path / "valid.zip", _valid_update_members())

    validate_update_archive(archive)


def test_validate_update_archive_accepts_python313_runtime(tmp_path: Path) -> None:
    members = _valid_update_members()
    members["秋招进程台账/_internal/python313.dll"] = members.pop(
        "秋招进程台账/_internal/python314.dll"
    )
    archive = _write_update_zip(tmp_path / "python313.zip", members)

    validate_update_archive(archive)


def test_validate_update_archive_requires_runtime(tmp_path: Path) -> None:
    members = _valid_update_members()
    del members["秋招进程台账/_internal/python314.dll"]
    archive = _write_update_zip(tmp_path / "missing-runtime.zip", members)

    with pytest.raises(UpdateError, match="运行时"):
        validate_update_archive(archive)


@pytest.mark.parametrize("unsafe_name", ["../outside.txt", "/absolute.txt", "C:/drive.txt"])
def test_validate_update_archive_rejects_unsafe_paths(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    members = _valid_update_members()
    members[unsafe_name] = b"unsafe"
    archive = _write_update_zip(tmp_path / "unsafe.zip", members)

    with pytest.raises(UpdateError, match="不安全"):
        validate_update_archive(archive)


def test_generated_updater_replaces_install_and_keeps_backup(tmp_path: Path) -> None:
    install_dir = tmp_path / "AutumnRecruitmentLedger"
    (install_dir / "_internal").mkdir(parents=True)
    (install_dir / "秋招进程台账.exe").write_bytes(b"old-exe")
    (install_dir / "_internal" / "python313.dll").write_bytes(b"old-runtime")
    (install_dir / "version.txt").write_text("old-version", encoding="utf-8")
    archive = _write_update_zip(tmp_path / "update.zip", _valid_update_members())
    script = write_updater_script(tmp_path / "apply-update.ps1")
    log_path = tmp_path / "update.log"

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ProcessId",
            "0",
            "-ArchivePath",
            str(archive),
            "-InstallDir",
            str(install_dir),
            "-ExecutableName",
            "秋招进程台账.exe",
            "-LogPath",
            str(log_path),
            "-NoRestart",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (install_dir / "version.txt").read_text(encoding="utf-8") == "new-version"
    backups = list(tmp_path.glob("AutumnRecruitmentLedger.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "version.txt").read_text(encoding="utf-8") == "old-version"
    assert "更新完成" in log_path.read_text(encoding="utf-8-sig")
