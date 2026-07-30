from __future__ import annotations

import subprocess
from pathlib import Path


SCRIPT_PATH = Path("scripts/sync_local_windows.ps1").resolve()


def _make_distribution(root: Path, version: str, include_runtime: bool = True) -> Path:
    root.mkdir(parents=True)
    (root / "秋招进程台账.exe").write_bytes(f"exe-{version}".encode())
    (root / "version.txt").write_text(version, encoding="utf-8")
    if include_runtime:
        internal = root / "_internal"
        internal.mkdir()
        (internal / "python313.dll").write_bytes(b"runtime")
    return root


def _run_sync(
    install_dir: Path,
    desktop_dir: Path,
    source_dist: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            "-InstallDir",
            str(install_dir),
            "-DesktopDir",
            str(desktop_dir),
            "-SourceDist",
            str(source_dist),
            "-SkipBuild",
            "-NoLaunch",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
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
    shortcut = desktop_dir / "秋招进程台账.lnk"
    assert shortcut.exists()
    assert Path(_shortcut_target(shortcut)) == install_dir / "秋招进程台账.exe"
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
    assert "python313.dll" in f"{result.stdout}\n{result.stderr}"
    assert (install_dir / "version.txt").read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob("installed.backup-*"))
