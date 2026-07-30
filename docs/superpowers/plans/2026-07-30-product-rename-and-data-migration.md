# Recruitment Record Ledger Rename and Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the active product to “招聘记录台账”, move active identifiers to the new brand, and migrate existing local data safely without renaming `autumn_recruitment.db`.

**Architecture:** Add a focused pre-start data migrator that copies the old SQLite database with the backup API and atomically installs it under the new application-data root. Then rename the Python package and every active distribution identifier while preserving explicit historical and database-name exceptions. Complete the stage with Windows build, local-install, portable-package, and migration verification; publishing occurs after the ordering plan is complete.

**Tech Stack:** Python 3.10+, PySide6, SQLite, pytest, pytest-qt, PyInstaller, PowerShell, Git, GitHub CLI.

## Global Constraints

- Product display name and executable are exactly `招聘记录台账` and `招聘记录台账.exe`.
- Python package is exactly `recruitment_ledger`.
- Main database filename remains exactly `autumn_recruitment.db`.
- New application identifier is exactly `RecruitmentRecordLedger`.
- New local repository path is `C:\Users\wty\Recruitment-Record-Ledger`.
- New GitHub repository is `wangtianyu-0403/Recruitment-Record-Ledger`.
- New Release asset is `Recruitment-Record-Ledger-Windows-x64.zip`.
- Old user data is never deleted or overwritten automatically.
- Active text files use UTF-8; user-visible errors are Chinese.
- Do not publish v1.1.2 until the ordering-and-pinning plan is also complete.

---

### Task 1: Safe legacy-data migration

**Files:**
- Create: `autumn_ledger/data_migration.py`
- Modify: `autumn_ledger/paths.py`
- Test: `tests/test_data_migration.py`

**Interfaces:**
- Consumes: `AppPaths.from_root(root: Path) -> AppPaths`
- Produces: `legacy_data_root(new_root: Path) -> Path`
- Produces: `migrate_legacy_data(new_paths: AppPaths, old_root: Path) -> bool`
- Produces: `DataMigrationError(RuntimeError)`

- [ ] **Step 1: Write failing migration tests**

Cover a new user, successful SQLite backup including committed WAL content, new-data precedence, corrupt legacy data, and copy-without-overwrite for backups/exports:

```python
def test_migrate_legacy_database_keeps_filename_and_source(tmp_path: Path) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    create_legacy_database(old_paths.database_path, company="旧记录")

    assert migrate_legacy_data(new_paths, old_paths.root) is True
    assert new_paths.database_path.name == "autumn_recruitment.db"
    assert read_company(new_paths.database_path) == "旧记录"
    assert read_company(old_paths.database_path) == "旧记录"


def test_existing_new_database_is_never_overwritten(tmp_path: Path) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    create_legacy_database(old_paths.database_path, company="旧")
    create_legacy_database(new_paths.database_path, company="新")

    assert migrate_legacy_data(new_paths, old_paths.root) is False
    assert read_company(new_paths.database_path) == "新"


def test_corrupt_legacy_database_does_not_leave_new_database(tmp_path: Path) -> None:
    old_paths = AppPaths.from_root(tmp_path / "AutumnRecruitmentLedger")
    new_paths = AppPaths.from_root(tmp_path / "RecruitmentRecordLedger")
    old_paths.database_path.parent.mkdir(parents=True)
    old_paths.database_path.write_bytes(b"not sqlite")

    with pytest.raises(DataMigrationError):
        migrate_legacy_data(new_paths, old_paths.root)
    assert not new_paths.database_path.exists()
    assert old_paths.database_path.read_bytes() == b"not sqlite"
```

- [ ] **Step 2: Run the migration tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_data_migration.py -q
```

Expected: collection fails because `autumn_ledger.data_migration` does not exist.

- [ ] **Step 3: Implement atomic migration**

Implement the migration around a temporary database in the new data directory:

```python
class DataMigrationError(RuntimeError):
    """旧版用户数据迁移失败。"""


def migrate_legacy_data(new_paths: AppPaths, old_root: Path) -> bool:
    old_paths = AppPaths.from_root(old_root)
    if new_paths.database_path.exists() or not old_paths.database_path.exists():
        return False
    new_paths.ensure_directories()
    temporary = new_paths.database_path.with_name(".migration.db")
    temporary.unlink(missing_ok=True)
    try:
        source_uri = f"{old_paths.database_path.as_uri()}?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(
            sqlite3.connect(temporary)
        ) as target:
            source.backup(target)
            integrity = target.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise DataMigrationError("旧数据库未通过 SQLite 完整性检查。")
        os.replace(temporary, new_paths.database_path)
        _copy_directory_contents(old_paths.backups_dir, new_paths.backups_dir)
        _copy_directory_contents(old_paths.exports_dir, new_paths.exports_dir)
        return True
    except DataMigrationError:
        temporary.unlink(missing_ok=True)
        raise
    except (OSError, sqlite3.Error) as exc:
        temporary.unlink(missing_ok=True)
        raise DataMigrationError(
            f"无法从“{old_paths.database_path}”迁移旧数据库：{exc}"
        ) from exc
```

`_copy_directory_contents` must copy files only when the destination does not exist and must not copy logs.

- [ ] **Step 4: Run focused tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_data_migration.py tests\test_database.py -q
git add autumn_ledger/paths.py autumn_ledger/data_migration.py tests/test_data_migration.py
git commit -m "feat: migrate legacy local data safely"
```

Expected: all focused tests pass.

### Task 2: Startup integration and backup-name transition

**Files:**
- Modify: `autumn_ledger/application.py`
- Modify: `autumn_ledger/backup.py`
- Modify: `autumn_ledger/paths.py`
- Test: `tests/test_application_startup.py`
- Test: `tests/test_backup.py`

**Interfaces:**
- Consumes: `migrate_legacy_data(new_paths, old_root) -> bool`
- Produces: `AppPaths.legacy_root_from_standard_paths() -> Path`
- Produces: daily backups named `recruitment_record_YYYYMMDD.db`

- [ ] **Step 1: Write failing startup and backup tests**

```python
def test_startup_migrates_before_database_initialization(monkeypatch, tmp_path):
    events: list[str] = []
    monkeypatch.setattr(AppPaths, "from_standard_paths", lambda: AppPaths.from_root(tmp_path / "new"))
    monkeypatch.setattr(application, "migrate_legacy_data", lambda paths, old: events.append("migrate") or False)
    monkeypatch.setattr(Database, "initialize", lambda self: events.append("initialize"))
    monkeypatch.setattr(application, "MainWindow", FakeWindow)

    application.run()

    assert events.index("migrate") < events.index("initialize")


def test_cleanup_counts_old_and_new_daily_backups_together(
    backup_manager, app_paths, monkeypatch
) -> None:
    create_named_backups(app_paths.backups_dir, old_count=20, new_count=20)
    backup_manager.cleanup_auto_backups(max_count=30)
    assert len(list(app_paths.backups_dir.glob("*.db"))) == 30
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_application_startup.py tests\test_backup.py -q
```

Expected: failures show missing startup migration and old backup naming.

- [ ] **Step 3: Integrate migration before database initialization**

Set the new Qt application name first, resolve new paths through
`QStandardPaths.AppDataLocation`, derive the sibling old application root without hard-coding
the user profile, and call:

```python
paths = AppPaths.from_standard_paths()
old_root = paths.root.parent / "AutumnRecruitmentLedger"
migrate_legacy_data(paths, old_root)
paths.ensure_directories()
configure_logging(paths.log_path)
database = Database(paths.database_path)
database.initialize()
```

Catch `DataMigrationError` through the existing startup error boundary. The Chinese error must
include the legacy source path and state that the source was retained.

- [ ] **Step 4: Transition backup and log names**

Set `log_path` to `recruitment_ledger.log`. Create future daily backups with:

```python
target = self.paths.backups_dir / f"recruitment_record_{current:%Y%m%d}.db"
```

Merge and sort both patterns for retention:

```python
files = {
    *self.paths.backups_dir.glob("autumn_recruitment_????????.db"),
    *self.paths.backups_dir.glob("recruitment_record_????????.db"),
}
```

- [ ] **Step 5: Run focused tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_application_startup.py tests\test_backup.py tests\test_database.py -q
git add autumn_ledger/application.py autumn_ledger/backup.py autumn_ledger/paths.py tests/test_application_startup.py tests/test_backup.py
git commit -m "feat: integrate renamed data paths"
```

Expected: all focused tests pass.

### Task 3: Active-code and product identifier rename

**Files:**
- Modify: `main.py`
- Modify: `recruitment_ledger/**/*.py`
- Modify: `tests/**/*.py`
- Modify: `AGENTS.md`
- Rename: `秋招进程台账.spec` to `招聘记录台账.spec`
- Rename: `秋招进程台账-debug.spec` to `招聘记录台账-debug.spec`

**Interfaces:**
- Produces: `APP_DISPLAY_NAME = "招聘记录台账"`
- Produces: `APP_VERSION = "1.1.2"`
- Produces: `APPLICATION_NAME = "RecruitmentRecordLedger"`

- [ ] **Step 1: Write failing branding tests**

Add exact assertions:

```python
def test_product_identity() -> None:
    assert APP_DISPLAY_NAME == "招聘记录台账"
    assert APP_VERSION == "1.1.2"
    assert APPLICATION_NAME == "RecruitmentRecordLedger"


def test_main_imports_renamed_package() -> None:
    source = Path("main.py").read_text(encoding="utf-8")
    assert "from recruitment_ledger.application import run" in source
    assert "autumn_ledger" not in source
```

- [ ] **Step 2: Run tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_product_identity.py -q
```

Expected: old display name, version, application identifier, and package import fail.

- [ ] **Step 3: Rename the package, active Python imports, and identity**

Move the package with validated, repository-contained source and destination paths:

```powershell
$repo = (Resolve-Path -LiteralPath ".").Path
$source = (Resolve-Path -LiteralPath ".\autumn_ledger").Path
$target = Join-Path $repo "recruitment_ledger"
if (-not $source.StartsWith($repo)) { throw "源目录越界" }
if (Test-Path -LiteralPath $target) { throw "目标包目录已经存在" }
Move-Item -LiteralPath $source -Destination $target
```

Mechanically replace imports from `autumn_ledger` with `recruitment_ledger` in `main.py`,
the renamed package, and tests. Update constants exactly:

```python
APP_DISPLAY_NAME = "招聘记录台账"
APP_VERSION = "1.1.2"
ORGANIZATION_NAME = "PersonalTools"
APPLICATION_NAME = "RecruitmentRecordLedger"
```

Rename the package docstring, temporary download prefixes, CSV export filename, and manual
backup filename to the new product vocabulary. Keep only the exact main-database filename
exception in active runtime code.

- [ ] **Step 4: Update PyInstaller spec and project rules**

Rename both tracked/working PyInstaller specs to the new product name. Set the release spec's
existing icon and application name to:

```python
name="招聘记录台账"
```

Update `AGENTS.md` to name `Recruitment-Record-Ledger` and `recruitment_ledger`, while
preserving all architectural and safety constraints.

- [ ] **Step 5: Run package and identity checks, then commit**

```powershell
.\.venv\Scripts\python.exe -m compileall -q recruitment_ledger
.\.venv\Scripts\python.exe -m pytest tests\test_product_identity.py tests\test_ui_smoke.py -q
git diff --check
git add main.py recruitment_ledger tests AGENTS.md "招聘记录台账.spec"
git add -u
git commit -m "refactor: rename product and Python package"
```

Expected: imports compile and focused tests pass.

### Task 4: Updater, Windows sync, build, and active documentation

**Files:**
- Modify: `recruitment_ledger/update.py`
- Modify: `scripts/build_windows.bat`
- Modify: `scripts/build_unix.sh`
- Modify: `scripts/sync_local_windows.ps1`
- Modify: `scripts/run_windows.bat`
- Modify: `scripts/run_unix.sh`
- Modify: `tests/test_update.py`
- Modify: `tests/test_sync_local_windows.py`
- Modify: `README.md`

**Interfaces:**
- Produces: updater asset `Recruitment-Record-Ledger-Windows-x64.zip`
- Produces: install root `%LOCALAPPDATA%\Programs\RecruitmentRecordLedger`
- Produces: desktop shortcut `招聘记录台账.lnk`

- [ ] **Step 1: Update failing updater and sync tests first**

Change fixtures and assertions to require:

```python
assert update.WINDOWS_ASSET_NAME == "Recruitment-Record-Ledger-Windows-x64.zip"
assert update.REPOSITORY_WEB_PATH == "/wangtianyu-0403/Recruitment-Record-Ledger"
assert update.UPDATE_ROOT_NAME == "招聘记录台账"
assert update.UPDATE_EXECUTABLE_NAME == "招聘记录台账.exe"
```

The sync test must assert the new install directory and shortcut, and must verify that an old
shortcut/install fixture is removed only after the new EXE exists.

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_update.py tests\test_sync_local_windows.py -q
```

Expected: old repository, asset, archive root, EXE, and install paths fail.

- [ ] **Step 3: Update release validation and updater script**

Set exact constants:

```python
LATEST_RELEASE_API = (
    "https://api.github.com/repos/"
    "wangtianyu-0403/Recruitment-Record-Ledger/releases/latest"
)
WINDOWS_ASSET_NAME = "Recruitment-Record-Ledger-Windows-x64.zip"
REPOSITORY_WEB_PATH = "/wangtianyu-0403/Recruitment-Record-Ledger"
USER_AGENT = "RecruitmentRecordLedger-Updater"
UPDATE_ROOT_NAME = "招聘记录台账"
UPDATE_EXECUTABLE_NAME = "招聘记录台账.exe"
```

Update the generated PowerShell installer to validate and launch the new EXE. Rename temporary
download/update prefixes to `recruitment-ledger-*`.

- [ ] **Step 4: Update build and local-sync scripts**

Build with `--onedir --windowed --icon assets\ui.ico --name "招聘记录台账"`.
Default local install is:

```powershell
Join-Path $env:LOCALAPPDATA "Programs\RecruitmentRecordLedger"
```

Stage the new program, verify `招聘记录台账.exe`, atomically install it, create
`招聘记录台账.lnk`, launch-test it, then remove only these exact old targets:

```powershell
$oldInstall = Join-Path $env:LOCALAPPDATA "Programs\AutumnRecruitmentLedger"
$oldShortcut = Join-Path $DesktopDir "秋招进程台账.lnk"
```

- [ ] **Step 5: Rewrite active README**

Document the new repository, product, data and install paths, one-time manual v1.1.1-to-v1.1.2
upgrade, unchanged database filename, local-only storage, migration backup behavior, build
commands, and the future “检查更新” workflow. Do not edit historical specs/plans to falsify
old releases.

- [ ] **Step 6: Run focused tests and active-name audit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_update.py tests\test_sync_local_windows.py tests\test_ui_smoke.py -q
rg -n "秋招进程台账|autumn-recruitment-ledger|AutumnRecruitmentLedger|from autumn_ledger|import autumn_ledger" main.py recruitment_ledger tests scripts README.md AGENTS.md
git diff --check
```

Expected: tests pass; the scan returns no matches except explicit legacy migration/cleanup test
fixtures and the unchanged `autumn_recruitment.db` policy documented in README.

- [ ] **Step 7: Commit**

```powershell
git add recruitment_ledger/update.py scripts tests/test_update.py tests/test_sync_local_windows.py README.md
git commit -m "build: rename Windows distribution and updater"
```

### Task 5: Rename local repository and verify the renamed baseline

**Files:**
- Rename outside Git: `C:\Users\wty\autumn-recruitment-ledger` to `C:\Users\wty\Recruitment-Record-Ledger`
- Update Git config: `origin`
- Verify: entire tracked tree

**Interfaces:**
- Consumes: all commits from Tasks 1–4
- Produces: clean renamed local repository ready for the ordering plan

- [ ] **Step 1: Run the full source test suite**

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q recruitment_ledger
git diff --check
git status --short
```

Expected: all tests pass; compilation and diff checks succeed; worktree is clean.

- [ ] **Step 2: Rename the repository directory safely**

From `C:\Users\wty`, resolve both paths, ensure the source is the expected Git repository and the
destination does not exist, then:

```powershell
Move-Item -LiteralPath "C:\Users\wty\autumn-recruitment-ledger" `
  -Destination "C:\Users\wty\Recruitment-Record-Ledger"
```

- [ ] **Step 3: Update and verify Git origin**

```powershell
git remote set-url origin https://github.com/wangtianyu-0403/Recruitment-Record-Ledger.git
git remote get-url origin
git ls-remote --exit-code origin HEAD
```

Run from `C:\Users\wty\Recruitment-Record-Ledger`.
Expected: both local origin and remote lookup use the new repository.

- [ ] **Step 4: Build and smoke-test the renamed application**

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ".\招聘记录台账.spec"
```

Expected: `dist\招聘记录台账\招聘记录台账.exe` exists, has the embedded icon, opens a
responding window titled `招聘记录台账`, and shows `版本v1.1.2`. Close only the verification
process.

- [ ] **Step 5: Verify a disposable legacy migration**

Run the built EXE with a disposable application-data setup containing an old
`AutumnRecruitmentLedger\data\autumn_recruitment.db`. Confirm the new
`RecruitmentRecordLedger\data\autumn_recruitment.db` contains the same records and the old file
still exists.

- [ ] **Step 6: Record the verified renamed baseline**

Smoke testing is expected to require no tracked correction. If a gate fails, stop and return to
the task that owns the failing file, add a regression test, fix it there, rerun that task's gate,
and commit with that task's stated commit message. Do not create an empty baseline commit.
