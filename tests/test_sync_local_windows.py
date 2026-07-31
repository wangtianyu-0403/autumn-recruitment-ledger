from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT_PATH = Path("scripts/sync_local_windows.ps1").resolve()


def _make_distribution(
    root: Path,
    version: str,
    *,
    executable: str = "招聘记录台账.exe",
    include_executable: bool = True,
    include_runtime: bool = True,
) -> Path:
    root.mkdir(parents=True)
    if include_executable:
        (root / executable).write_bytes(f"exe-{version}".encode())
    (root / "version.txt").write_text(version, encoding="utf-8")
    if include_runtime:
        internal = root / "_internal"
        internal.mkdir()
        (internal / "python313.dll").write_bytes(b"runtime")
    return root


def _run_sync(
    install_dir: Path | None,
    desktop_dir: Path,
    source_dist: Path,
    *,
    local_app_data: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCRIPT_PATH),
        "-DesktopDir",
        str(desktop_dir),
        "-SourceDist",
        str(source_dist),
        "-SkipBuild",
        "-NoLaunch",
    ]
    if install_dir is not None:
        command.extend(["-InstallDir", str(install_dir)])
    environment = os.environ.copy()
    if local_app_data is not None:
        environment["LOCALAPPDATA"] = str(local_app_data)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        env=environment,
    )


def _shortcut_target(shortcut_path: Path) -> str:
    command = (
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
        "$ws=New-Object -ComObject WScript.Shell;"
        f"$sc=$ws.CreateShortcut('{shortcut_path}');"
        "Write-Output $sc.TargetPath"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=True,
    )
    return result.stdout.strip()


def test_local_sync_replaces_install_and_repairs_shortcut(tmp_path: Path) -> None:
    install_dir = _make_distribution(tmp_path / "installed", "old")
    source_dist = _make_distribution(tmp_path / "new-dist", "v1.1.0")
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()

    result = _run_sync(install_dir, desktop_dir, source_dist)

    assert result.returncode == 0, result.stderr
    assert (install_dir / "version.txt").read_text(encoding="utf-8") == "v1.1.0"
    shortcut = desktop_dir / "招聘记录台账.lnk"
    assert shortcut.exists()
    assert Path(_shortcut_target(shortcut)) == install_dir / "招聘记录台账.exe"
    backups = list(tmp_path.glob("installed.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "version.txt").read_text(encoding="utf-8") == "old"


def test_local_sync_rejects_incomplete_dist_without_touching_install(
    tmp_path: Path,
) -> None:
    install_dir = _make_distribution(tmp_path / "installed", "old")
    source_dist = _make_distribution(
        tmp_path / "incomplete-dist",
        "broken",
        include_runtime=False,
    )
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()

    result = _run_sync(install_dir, desktop_dir, source_dist)

    assert result.returncode != 0
    assert "python3NN.dll" in f"{result.stdout}\n{result.stderr}"
    assert (install_dir / "version.txt").read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob("installed.backup-*"))


def test_default_sync_removes_legacy_targets_only_after_new_exe_exists(
    tmp_path: Path,
) -> None:
    local_app_data = tmp_path / "LocalAppData"
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    old_install = _make_distribution(
        local_app_data / "Programs" / "AutumnRecruitmentLedger",
        "v1.1.1",
        executable="秋招进程台账.exe",
    )
    old_shortcut = desktop_dir / "秋招进程台账.lnk"
    old_shortcut.write_bytes(b"legacy shortcut fixture")
    incomplete_dist = _make_distribution(
        tmp_path / "incomplete-new-dist",
        "v1.1.2",
        include_executable=False,
    )

    failed = _run_sync(
        None,
        desktop_dir,
        incomplete_dist,
        local_app_data=local_app_data,
    )

    new_install = local_app_data / "Programs" / "RecruitmentRecordLedger"
    assert failed.returncode != 0
    assert old_install.exists()
    assert old_shortcut.exists()
    assert not new_install.exists()
    assert not (desktop_dir / "招聘记录台账.lnk").exists()

    complete_dist = _make_distribution(tmp_path / "complete-new-dist", "v1.1.2")
    succeeded = _run_sync(
        None,
        desktop_dir,
        complete_dist,
        local_app_data=local_app_data,
    )

    assert succeeded.returncode == 0, succeeded.stderr
    assert (new_install / "招聘记录台账.exe").exists()
    new_shortcut = desktop_dir / "招聘记录台账.lnk"
    assert new_shortcut.exists()
    assert Path(_shortcut_target(new_shortcut)) == (
        new_install / "招聘记录台账.exe"
    )
    assert not old_install.exists()
    assert not old_shortcut.exists()


def test_custom_legacy_install_target_keeps_newly_installed_executable(
    tmp_path: Path,
) -> None:
    local_app_data = tmp_path / "LocalAppData"
    legacy_install = _make_distribution(
        local_app_data / "Programs" / "AutumnRecruitmentLedger",
        "v1.1.1",
        executable="秋招进程台账.exe",
    )
    source_dist = _make_distribution(tmp_path / "new-dist", "v1.1.2")
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()

    result = _run_sync(
        legacy_install,
        desktop_dir,
        source_dist,
        local_app_data=local_app_data,
    )

    assert result.returncode == 0, result.stderr
    assert (legacy_install / "招聘记录台账.exe").exists()
    assert (legacy_install / "version.txt").read_text(encoding="utf-8") == "v1.1.2"
