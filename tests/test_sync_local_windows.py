from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


SCRIPT_PATH = Path("scripts/sync_local_windows.ps1").resolve()


def _make_distribution(
    root: Path,
    version: str,
    *,
    executable: str = "招聘记录台账.exe",
    executable_source: Path | None = None,
    include_executable: bool = True,
    include_runtime: bool = True,
) -> Path:
    root.mkdir(parents=True)
    if include_executable:
        executable_path = root / executable
        if executable_source is None:
            executable_path.write_bytes(f"exe-{version}".encode())
        else:
            shutil.copy2(executable_source, executable_path)
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
    no_launch: bool = True,
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
    ]
    if no_launch:
        command.append("-NoLaunch")
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


def _create_shortcut(shortcut_path: Path, target_path: Path) -> None:
    command = (
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
        "$ws=New-Object -ComObject WScript.Shell;"
        f"$sc=$ws.CreateShortcut('{shortcut_path}');"
        f"$sc.TargetPath='{target_path}';"
        f"$sc.WorkingDirectory='{target_path.parent}';"
        "$sc.Arguments='--preserve-original-shortcut';"
        "$sc.Description='original shortcut state';"
        "$sc.Save()"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=True,
    )


def _compile_health_probe(destination: Path, title: str | None) -> Path:
    compiler_candidates = (
        Path(os.environ["SystemRoot"])
        / "Microsoft.NET"
        / "Framework64"
        / "v4.0.30319"
        / "csc.exe",
        Path(os.environ["SystemRoot"])
        / "Microsoft.NET"
        / "Framework"
        / "v4.0.30319"
        / "csc.exe",
    )
    compiler = next(path for path in compiler_candidates if path.exists())
    if title is None:
        run_body = "Thread.Sleep(15000);"
    else:
        escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
        run_body = f"""
        Application.EnableVisualStyles();
        using (var form = new Form())
        {{
            form.Text = \"{escaped_title}\";
            var timer = new System.Windows.Forms.Timer();
            timer.Interval = 15000;
            timer.Tick += delegate {{ form.Close(); }};
            timer.Start();
            Application.Run(form);
        }}
"""
    source = destination.with_suffix(".cs")
    source.write_text(
        f"""
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Windows.Forms;

internal static class Program
{{
    [STAThread]
    private static void Main()
    {{
        File.WriteAllText(
            Path.Combine(Environment.CurrentDirectory, \"health-test.pid\"),
            Process.GetCurrentProcess().Id.ToString()
        );
        {run_body}
    }}
}}
""",
        encoding="utf-8-sig",
    )
    result = subprocess.run(
        [
            str(compiler),
            "/nologo",
            "/target:winexe",
            f"/out:{destination}",
            "/reference:System.Windows.Forms.dll",
            "/reference:System.Drawing.dll",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return destination


def _stop_health_probes(test_root: Path) -> None:
    for pid_file in test_root.rglob("health-test.pid"):
        try:
            process_id = int(pid_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        command = (
            f"$candidate=Get-CimInstance Win32_Process -Filter \"ProcessId = {process_id}\" "
            "-ErrorAction SilentlyContinue;"
            f"$testRoot=[IO.Path]::GetFullPath('{test_root}');"
            "if ($candidate -and $candidate.ExecutablePath -and "
            "[IO.Path]::GetFullPath($candidate.ExecutablePath).StartsWith("
            "$testRoot,[StringComparison]::OrdinalIgnoreCase)) {"
            f"Stop-Process -Id {process_id} -Force -ErrorAction SilentlyContinue"
            "}"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )


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


def test_default_sync_without_launch_keeps_legacy_targets_after_install(
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
    complete_dist = _make_distribution(tmp_path / "complete-new-dist", "v1.1.2")
    succeeded = _run_sync(
        None,
        desktop_dir,
        complete_dist,
        local_app_data=local_app_data,
    )

    new_install = local_app_data / "Programs" / "RecruitmentRecordLedger"
    assert succeeded.returncode == 0, succeeded.stderr
    assert (new_install / "招聘记录台账.exe").exists()
    new_shortcut = desktop_dir / "招聘记录台账.lnk"
    assert new_shortcut.exists()
    assert Path(_shortcut_target(new_shortcut)) == (
        new_install / "招聘记录台账.exe"
    )
    assert old_install.exists()
    assert old_shortcut.exists()


def test_default_sync_failed_launch_keeps_legacy_targets(tmp_path: Path) -> None:
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
    invalid_dist = _make_distribution(tmp_path / "invalid-dist", "v1.1.2")

    result = _run_sync(
        None,
        desktop_dir,
        invalid_dist,
        local_app_data=local_app_data,
        no_launch=False,
    )

    assert result.returncode != 0
    assert old_install.exists()
    assert old_shortcut.exists()


def test_default_sync_cleans_legacy_targets_after_verified_launch(
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
    health_probe = _compile_health_probe(
        tmp_path / "healthy-window.exe", "招聘记录台账"
    )
    runnable_dist = _make_distribution(
        tmp_path / "runnable-dist",
        "v1.1.2",
        executable_source=health_probe,
    )

    try:
        result = _run_sync(
            None,
            desktop_dir,
            runnable_dist,
            local_app_data=local_app_data,
            no_launch=False,
        )

        assert result.returncode == 0, result.stderr
        new_install = local_app_data / "Programs" / "RecruitmentRecordLedger"
        assert (new_install / "招聘记录台账.exe").exists()
        assert not old_install.exists()
        assert not old_shortcut.exists()
    finally:
        _stop_health_probes(tmp_path)


def test_zero_code_early_exit_restores_existing_install_and_shortcut(
    tmp_path: Path,
) -> None:
    install_dir = _make_distribution(tmp_path / "installed", "original")
    source_dist = _make_distribution(
        tmp_path / "zero-exit-dist",
        "replacement",
        executable_source=Path(os.environ["SystemRoot"]) / "System32" / "whoami.exe",
    )
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    shortcut = desktop_dir / "招聘记录台账.lnk"
    _create_shortcut(shortcut, install_dir / "招聘记录台账.exe")
    original_shortcut = shortcut.read_bytes()

    result = _run_sync(
        install_dir,
        desktop_dir,
        source_dist,
        no_launch=False,
    )

    assert result.returncode != 0
    assert "过早退出" in f"{result.stdout}\n{result.stderr}"
    assert (install_dir / "version.txt").read_text(encoding="utf-8") == "original"
    assert shortcut.read_bytes() == original_shortcut


def test_shortcut_save_failure_restores_existing_install_and_shortcut(
    tmp_path: Path,
) -> None:
    install_dir = _make_distribution(tmp_path / "installed", "original")
    source_dist = _make_distribution(tmp_path / "new-dist", "replacement")
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    shortcut = desktop_dir / "招聘记录台账.lnk"
    _create_shortcut(shortcut, install_dir / "招聘记录台账.exe")
    original_shortcut = shortcut.read_bytes()
    shortcut.chmod(stat.S_IREAD)

    try:
        result = _run_sync(install_dir, desktop_dir, source_dist)

        assert result.returncode != 0
        assert (install_dir / "version.txt").read_text(encoding="utf-8") == "original"
        assert shortcut.read_bytes() == original_shortcut
    finally:
        if shortcut.exists():
            shortcut.chmod(stat.S_IWRITE)


def test_wrong_window_title_restores_existing_install_and_shortcut(
    tmp_path: Path,
) -> None:
    install_dir = _make_distribution(tmp_path / "installed", "original")
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    shortcut = desktop_dir / "招聘记录台账.lnk"
    _create_shortcut(shortcut, install_dir / "招聘记录台账.exe")
    original_shortcut = shortcut.read_bytes()
    wrong_window = _compile_health_probe(tmp_path / "wrong-window.exe", "错误标题")
    source_dist = _make_distribution(
        tmp_path / "wrong-window-dist",
        "replacement",
        executable_source=wrong_window,
    )

    try:
        result = _run_sync(
            install_dir,
            desktop_dir,
            source_dist,
            no_launch=False,
        )

        assert result.returncode != 0
        assert "窗口" in f"{result.stdout}\n{result.stderr}"
        assert (install_dir / "version.txt").read_text(encoding="utf-8") == "original"
        assert shortcut.read_bytes() == original_shortcut
    finally:
        _stop_health_probes(tmp_path)


def test_missing_main_window_fails_and_removes_active_install(tmp_path: Path) -> None:
    install_dir = tmp_path / "installed"
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    headless_probe = _compile_health_probe(tmp_path / "headless.exe", None)
    source_dist = _make_distribution(
        tmp_path / "headless-dist",
        "replacement",
        executable_source=headless_probe,
    )

    try:
        result = _run_sync(
            install_dir,
            desktop_dir,
            source_dist,
            no_launch=False,
        )

        assert result.returncode != 0
        assert "窗口" in f"{result.stdout}\n{result.stderr}"
        assert not install_dir.exists()
        assert not (desktop_dir / "招聘记录台账.lnk").exists()
    finally:
        _stop_health_probes(tmp_path)


def test_running_legacy_executable_stops_sync_before_any_write(tmp_path: Path) -> None:
    local_app_data = tmp_path / "LocalAppData"
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir()
    old_install = _make_distribution(
        local_app_data / "Programs" / "AutumnRecruitmentLedger",
        "v1.1.1",
        executable="秋招进程台账.exe",
        executable_source=Path(os.environ["SystemRoot"]) / "System32" / "ping.exe",
    )
    old_shortcut = desktop_dir / "秋招进程台账.lnk"
    old_shortcut.write_bytes(b"legacy shortcut fixture")
    source_dist = _make_distribution(tmp_path / "new-dist", "v1.1.2")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    legacy_process = subprocess.Popen(
        [str(old_install / "秋招进程台账.exe"), "-t", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )

    try:
        result = _run_sync(
            None,
            desktop_dir,
            source_dist,
            local_app_data=local_app_data,
        )

        new_install = local_app_data / "Programs" / "RecruitmentRecordLedger"
        assert result.returncode != 0
        assert (old_install / "version.txt").read_text(encoding="utf-8") == "v1.1.1"
        assert old_shortcut.exists()
        assert not new_install.exists()
        assert not (desktop_dir / "招聘记录台账.lnk").exists()
        assert not list((local_app_data / "Programs").glob("*.staging-*"))
        assert not list((local_app_data / "Programs").glob("*.backup-*"))
    finally:
        legacy_process.terminate()
        legacy_process.wait(timeout=10)


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
