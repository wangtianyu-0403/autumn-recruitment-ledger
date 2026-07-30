# Manual Updater and Local Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-triggered, SHA-256-verified GitHub Release updater and a developer one-click Windows sync workflow, then publish both as v1.1.0.

**Architecture:** Keep release parsing, downloading, ZIP validation, and updater-script generation in a standalone `autumn_ledger.update` module. The main window owns only user interaction, while PowerShell performs post-exit replacement; a separate parameterized PowerShell script handles local developer build/install and is exercised against temporary fake distributions.

**Tech Stack:** Python 3.13 standard library, PySide6, pytest/pytest-qt, PowerShell 5.1+, PyInstaller 6.21, GitHub Releases API.

## Global Constraints

- Update checks occur only after the user clicks “检查更新”.
- Only non-draft, non-prerelease semantic versions and the exact asset `autumn-recruitment-ledger-Windows-x64.zip` are accepted.
- The downloaded asset must match a GitHub `sha256:` digest.
- ZIP paths must not be absolute or escape extraction with `..`.
- Program replacement must not touch `%APPDATA%\PersonalTools\AutumnRecruitmentLedger\`.
- Source mode may check versions but must not self-replace.
- Windows 10/11 64-bit is the only automatic-update target.
- The feature ships as v1.1.0; v1.0.0 remains unchanged.

---

### Task 1: Release Metadata and Version Rules

**Files:**
- Create: `autumn_ledger/update.py`
- Create: `tests/test_update.py`

**Interfaces:**
- Produces: `UpdateError`
- Produces: `ReleaseInfo(version, tag_name, asset_url, asset_digest, html_url)`
- Produces: `parse_version(value: str) -> tuple[int, int, int]`
- Produces: `fetch_latest_release(api_url: str = LATEST_RELEASE_API, timeout: float = 10.0) -> ReleaseInfo`

- [ ] **Step 1: Write failing tests**

Test literal outcomes for `v1.2.3`, `1.2.3`, invalid segment counts, non-numeric values, draft/prerelease responses, missing assets, and a valid JSON response loaded through a temporary `file://` URL.

- [ ] **Step 2: Verify RED**

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
C:\Users\wty\autumn-recruitment-ledger\.venv\Scripts\python.exe -m pytest tests/test_update.py -q
```

Expected: import failure because `autumn_ledger.update` does not exist.

- [ ] **Step 3: Implement metadata parsing**

Use `urllib.request.Request`/`urlopen`, JSON decoding, explicit schema checks, semantic tuple parsing, and Chinese `UpdateError` messages. Reject digests not beginning with `sha256:`.

- [ ] **Step 4: Verify GREEN**

Run `tests/test_update.py`; expected all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add autumn_ledger/update.py tests/test_update.py
git commit -m "feat: add release update metadata"
```

### Task 2: Verified Download, ZIP Safety, and External Replacement

**Files:**
- Modify: `autumn_ledger/update.py`
- Modify: `tests/test_update.py`

**Interfaces:**
- Produces: `download_release_asset(release, destination, progress=None, timeout=60.0) -> Path`
- Produces: `validate_update_archive(archive_path: Path) -> None`
- Produces: `write_updater_script(script_path: Path) -> Path`
- Produces: `launch_updater(archive_path: Path, install_dir: Path, executable_path: Path) -> Path`

- [ ] **Step 1: Write failing download and archive tests**

Use a temporary source file through `file://`; assert correct digest succeeds, wrong digest fails, required ZIP entries pass, missing runtime fails, and absolute/parent-traversal entries fail.

- [ ] **Step 2: Write a failing replacement-helper test**

Generate the PowerShell script, create a fake old install directory and valid ZIP containing a fake new EXE/runtime, run the script with process ID `0` and `-NoRestart`, and assert the new sentinel replaces the old sentinel while a backup remains.

- [ ] **Step 3: Verify RED**

Run `tests/test_update.py`; expected failures for missing functions.

- [ ] **Step 4: Implement download and archive validation**

Stream bytes in chunks, update SHA-256 during download, invoke optional progress with `(downloaded, total)`, compare lowercase hex digest, and validate `zipfile.PurePosixPath` members before installation.

- [ ] **Step 5: Implement and exercise the PowerShell helper**

The generated script must:

1. wait for `ProcessId` when greater than zero;
2. extract to a sibling staging directory;
3. verify EXE and a versioned `_internal/python3NN.dll`;
4. move the old install to a timestamped backup;
5. move the staged app into the original path;
6. restart unless `-NoRestart`;
7. restore the backup on failure;
8. append messages to the supplied log.

- [ ] **Step 6: Verify GREEN and full regression**

Run `tests/test_update.py` and `python -m pytest -q`.

- [ ] **Step 7: Commit**

```powershell
git add autumn_ledger/update.py tests/test_update.py
git commit -m "feat: verify and install release updates"
```

### Task 3: Manual Main-Window Update Interaction

**Files:**
- Modify: `autumn_ledger/constants.py`
- Modify: `autumn_ledger/ui/main_window.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `APP_VERSION`, `fetch_latest_release`, `download_release_asset`, `validate_update_archive`, `launch_updater`
- Produces: `MainWindow.check_update_button`
- Produces: `MainWindow.check_for_updates() -> None`

- [ ] **Step 1: Write failing UI tests**

Assert the toolbar button text is `检查更新`. Inject a valid `ReleaseInfo` via monkeypatch and intercept `QMessageBox.information` to verify the no-update message; verify source mode with a newer release never invokes download/install.

- [ ] **Step 2: Verify RED**

Run the focused UI tests; expected failure because the button and handler do not exist.

- [ ] **Step 3: Bump version and implement the button**

Set `APP_VERSION = "1.1.0"`. Add “检查更新” to the toolbar and implement:

- wait cursor during metadata request;
- no-update information dialog;
- confirmation dialog for a newer version;
- source-mode instruction to run `scripts\sync_local_windows.bat`;
- frozen-mode temporary download, progress dialog, archive validation, updater launch, and application quit;
- Chinese error dialog for `UpdateError`.

- [ ] **Step 4: Verify GREEN**

Run focused UI tests and the complete suite.

- [ ] **Step 5: Commit**

```powershell
git add autumn_ledger/constants.py autumn_ledger/ui/main_window.py tests/test_ui_smoke.py
git commit -m "feat: add manual update action"
```

### Task 4: Developer Local Sync Scripts

**Files:**
- Create: `scripts/sync_local_windows.ps1`
- Create: `scripts/sync_local_windows.bat`
- Create: `tests/test_sync_local_windows.py`

**Interfaces:**
- PowerShell parameters: `InstallDir`, `DesktopDir`, `SourceDist`, `SkipBuild`, `NoLaunch`
- Default install: `%LOCALAPPDATA%\Programs\AutumnRecruitmentLedger`

- [ ] **Step 1: Write failing integration tests**

From pytest, run PowerShell with `-SkipBuild -NoLaunch` against temporary fake distributions. Assert:

- a valid distribution replaces an old sentinel;
- the desktop shortcut targets the stable EXE;
- a missing versioned `_internal/python3NN.dll` returns non-zero and preserves the old sentinel.

- [ ] **Step 2: Verify RED**

Run `tests/test_sync_local_windows.py`; expected failure because the script is absent.

- [ ] **Step 3: Implement the parameterized PowerShell script**

Default mode installs dependencies, runs tests offscreen, builds PyInstaller onedir, validates the distribution, refuses replacement when the installed EXE is running, swaps through a temporary directory with rollback, repairs the shortcut, and starts the app unless `NoLaunch`.

- [ ] **Step 4: Add the batch entry point**

Invoke:

```bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_local_windows.ps1"
```

and preserve the exit code.

- [ ] **Step 5: Verify GREEN and full regression**

Run the sync integration tests and complete pytest suite.

- [ ] **Step 6: Commit**

```powershell
git add scripts/sync_local_windows.ps1 scripts/sync_local_windows.bat tests/test_sync_local_windows.py
git commit -m "feat: add one-click local sync"
```

### Task 5: Documentation, Packaging, and v1.1.0 Release

**Files:**
- Modify: `README.md`
- Rebuild ignored: `build/`, `dist/`
- Replace outside Git: `outputs/秋招进程台账-Windows-x64.zip`

**Interfaces:**
- Produces: pushed `main` and public Release `v1.1.0`

- [ ] **Step 1: Update README**

Document the manual “检查更新” button, local sync batch file, stable local installation directory, backup/rollback behavior, and the requirement that future releases use the exact ASCII asset name.

- [ ] **Step 2: Run final source verification**

Run `python -m compileall -q autumn_ledger`, `git diff --check`, and full pytest.

- [ ] **Step 3: Build and audit the ZIP**

Build PyInstaller onedir, add `使用说明.txt`, reject private/source/build patterns, compress, verify SHA-256, and launch from a Chinese-and-space extraction path.

- [ ] **Step 4: Exercise local one-click sync**

Run `scripts/sync_local_windows.ps1` in default build mode with `-NoLaunch`, verify `%LOCALAPPDATA%\Programs\AutumnRecruitmentLedger\秋招进程台账.exe`, and verify the desktop shortcut target.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md
git commit -m "docs: explain manual and local updates"
```

- [ ] **Step 6: Merge and push after final review**

Fast-forward the feature branch into `main`, rerun the complete suite on `main`, and push `main`.

- [ ] **Step 7: Publish v1.1.0**

Create GitHub Release `v1.1.0` with the ASCII-named ZIP asset, version-specific notes, and the exact SHA-256.

- [ ] **Step 8: Verify remote state**

Read back remote README, release metadata, asset name/size/digest, HTTP 200 download, tag, and remote `main`; all must match local evidence.
