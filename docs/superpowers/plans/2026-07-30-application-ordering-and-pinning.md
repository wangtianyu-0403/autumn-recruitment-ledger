# Application Ordering and Pinning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent drag ordering, explicit pinning, application-date sorting, and last-update sorting to the renamed v1.1.2 application.

**Architecture:** Extend the existing applications table with pin and manual-order metadata, then expose a whitelist-based repository API and a service-owned visible-subset reorder algorithm. A focused QTableWidget subclass emits application IDs after drag/drop, while MainWindow manages sorting preferences and pin actions without issuing SQL.

**Tech Stack:** Python 3.10+, PySide6, SQLite, pytest, pytest-qt, PyInstaller, PowerShell, Git, GitHub CLI.

## Global Constraints

- Execute after `2026-07-30-product-rename-and-data-migration.md`.
- All Python imports use `recruitment_ledger`.
- Database schema upgrades preserve every existing application and status-history record.
- `is_pinned` and `manual_order` are internal fields and are not exported to CSV.
- Pinned records precede unpinned records in every sort mode.
- Application-date and last-update sorts are newest first.
- Dragging in an automatic mode switches to manual mode.
- Filtered dragging changes only the relative order of visible records.
- Pinning does not modify `updated_at`.
- Version remains `1.1.2`.

---

### Task 1: Schema v2 and ordering model fields

**Files:**
- Modify: `recruitment_ledger/database.py`
- Modify: `recruitment_ledger/models.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Produces: `Database.SCHEMA_VERSION = 2`
- Produces: `ApplicationRecord.is_pinned: bool`
- Produces: `ApplicationRecord.manual_order: int`

- [ ] **Step 1: Write failing schema-migration tests**

Create a version-1 database fixture with records ordered by `updated_at DESC, id DESC`, initialize
it with the new `Database`, then assert:

```python
columns = {
    row["name"]
    for row in database.connection.execute("PRAGMA table_info(applications)")
}
assert {"is_pinned", "manual_order"} <= columns
assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 2
rows = database.connection.execute(
    "SELECT id, is_pinned, manual_order FROM applications ORDER BY manual_order"
).fetchall()
assert [row["id"] for row in rows] == expected_old_default_order
assert all(row["is_pinned"] == 0 for row in rows)
```

Also initialize twice and assert the second initialization does not change `manual_order`.

- [ ] **Step 2: Run schema tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_database.py -q
```

Expected: schema version and missing-column assertions fail.

- [ ] **Step 3: Implement transactional schema v2 migration**

Set `SCHEMA_VERSION = 2`. After the version-1 schema exists, migrate only when
`PRAGMA user_version < 2`:

```python
connection.execute(
    "ALTER TABLE applications ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0"
)
connection.execute(
    "ALTER TABLE applications ADD COLUMN manual_order INTEGER NOT NULL DEFAULT 0"
)
rows = connection.execute(
    "SELECT id FROM applications ORDER BY updated_at DESC, id DESC"
).fetchall()
connection.executemany(
    "UPDATE applications SET manual_order = ? WHERE id = ?",
    ((index, row["id"]) for index, row in enumerate(rows)),
)
connection.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_applications_active_order
    ON applications(is_deleted, is_pinned DESC, manual_order, id)
    """
)
connection.execute("PRAGMA user_version = 2")
```

For brand-new databases, create both columns in the base `CREATE TABLE` statement and still set
`user_version = 2`. Guard migrations by detected columns so a partially hand-modified database
receives only missing columns.

- [ ] **Step 4: Extend the dataclass mapping**

Add:

```python
is_pinned: bool = False
manual_order: int = 0
```

and map both from `sqlite3.Row` in `ApplicationRecord.from_row`.

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_database.py tests\test_repository.py -q
git add recruitment_ledger/database.py recruitment_ledger/models.py tests/test_database.py tests/test_repository.py
git commit -m "feat: add persistent ordering schema"
```

Expected: schema and existing repository tests pass.

### Task 2: Repository sorting, pinning, and full-order persistence

**Files:**
- Modify: `recruitment_ledger/repository.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Produces: `SortMode(str, Enum)` values `manual`, `application_date`, `updated_at`
- Produces: `list_applications(..., sort_mode: SortMode = SortMode.UPDATED_AT)`
- Produces: `set_pinned(application_id: int, pinned: bool) -> None`
- Produces: `save_manual_order(application_ids: Sequence[int], pinned: bool) -> None`
- Produces: `list_active_ids(sort_mode: SortMode) -> list[int]`

- [ ] **Step 1: Write failing repository behavior tests**

Add tests for all modes, stable ties, pinned-first behavior, no `updated_at` change on pinning,
invalid/duplicate IDs, and transactional persistence:

```python
def test_pinned_records_precede_automatic_sort(repository):
    older = create_record(repository, application_date="2026-01-01")
    newer = create_record(repository, application_date="2026-07-30")
    repository.set_pinned(older, True)

    records = repository.list_applications(sort_mode=SortMode.APPLICATION_DATE)

    assert [record.id for record in records] == [older, newer]


def test_save_manual_order_rejects_duplicate_ids(repository):
    app_id = create_record(repository)
    with pytest.raises(RepositoryError):
        repository.save_manual_order([app_id, app_id], pinned=False)
```

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_repository.py -q
```

Expected: missing enum and repository methods fail.

- [ ] **Step 3: Implement a whitelist sort enum**

```python
class SortMode(str, Enum):
    MANUAL = "manual"
    APPLICATION_DATE = "application_date"
    UPDATED_AT = "updated_at"


_ORDER_BY = {
    SortMode.MANUAL: "is_pinned DESC, manual_order ASC, id ASC",
    SortMode.APPLICATION_DATE:
        "is_pinned DESC, application_date DESC, manual_order ASC, id DESC",
    SortMode.UPDATED_AT:
        "is_pinned DESC, updated_at DESC, manual_order ASC, id DESC",
}
```

Coerce input with `SortMode(sort_mode)` and raise `RepositoryError("未知排序模式。")` on invalid
values. Never interpolate user-provided SQL.

- [ ] **Step 4: Implement pin and order transactions**

`set_pinned` must verify one active record, set `is_pinned`, and move it to the top of its new
group without updating `updated_at`. `save_manual_order` must verify that the supplied IDs are
unique and exactly equal to the active IDs in the requested pin group, then update all rows in
one transaction:

```python
connection.executemany(
    "UPDATE applications SET manual_order = ? WHERE id = ?",
    ((index, application_id) for index, application_id in enumerate(application_ids)),
)
```

New records receive one less than the current minimum order in the unpinned group, then the group
may be normalized. Soft delete and restore must leave both ordering fields unchanged.

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_repository.py tests\test_database.py -q
git add recruitment_ledger/repository.py tests/test_repository.py
git commit -m "feat: persist sort modes and pin state"
```

### Task 3: Service-owned filtered reorder algorithm

**Files:**
- Modify: `recruitment_ledger/services.py`
- Create: `tests/test_services.py`

**Interfaces:**
- Consumes: repository methods from Task 2
- Produces: `list(..., sort_mode: SortMode = SortMode.UPDATED_AT)`
- Produces: `set_pinned(application_id: int, pinned: bool) -> None`
- Produces: `reorder_visible(visible_ids: Sequence[int], sort_mode: SortMode) -> None`

- [ ] **Step 1: Write failing service tests**

Use a fake repository to prove that filtered reorder replaces only visible slots:

```python
def test_reorder_visible_preserves_hidden_slots():
    repository = FakeRepository(
        pinned_ids=[],
        unpinned_ids=[1, 2, 3, 4, 5],
    )
    service = ApplicationService(repository)

    service.reorder_visible([4, 2], SortMode.MANUAL)

    assert repository.saved_unpinned == [1, 4, 3, 2, 5]


def test_reorder_visible_keeps_pin_groups_separate():
    repository = FakeRepository(pinned_ids=[1, 2], unpinned_ids=[3, 4])
    service = ApplicationService(repository)

    service.reorder_visible([3, 2, 1, 4], SortMode.MANUAL)

    assert repository.saved_pinned == [2, 1]
    assert repository.saved_unpinned == [3, 4]
```

- [ ] **Step 2: Run service tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_services.py -q
```

Expected: missing service methods fail.

- [ ] **Step 3: Implement visible-slot replacement**

Validate non-null, unique, active IDs. Split visible IDs by pin group and, for each affected
group, replace only slots occupied by visible IDs:

```python
def _merge_visible_order(full_ids: Sequence[int], visible_ids: Sequence[int]) -> list[int]:
    visible_set = set(visible_ids)
    iterator = iter(visible_ids)
    return [next(iterator) if value in visible_set else value for value in full_ids]
```

When `sort_mode` is automatic, obtain the entire active order in that mode and save it as manual
order before applying the visible move. Then persist each affected pin group through
`save_manual_order`.

- [ ] **Step 4: Delegate list and pin calls**

Pass `sort_mode` into repository listing and expose:

```python
def set_pinned(self, application_id: int, pinned: bool) -> None:
    self.repository.set_pinned(application_id, pinned)
```

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_services.py tests\test_repository.py -q
git add recruitment_ledger/services.py tests/test_services.py
git commit -m "feat: add safe filtered row reordering"
```

### Task 4: Drag-aware table and pin action widget

**Files:**
- Create: `recruitment_ledger/ui/application_table.py`
- Modify: `recruitment_ledger/ui/widgets.py`
- Create: `tests/test_application_table.py`
- Modify: `tests/test_ui_widgets.py`

**Interfaces:**
- Produces: `ApplicationTableWidget(QTableWidget)`
- Produces signal: `rows_reordered = Signal(list)`
- Produces: `set_application_ids(application_ids: Sequence[int]) -> None`
- Extends signal: `ActionCell.pin_requested = Signal(int, bool)`

- [ ] **Step 1: Write failing widget tests**

```python
def test_action_cell_emits_pin_request(qtbot):
    cell = ActionCell(application_id=7, is_pinned=False)
    qtbot.addWidget(cell)
    with qtbot.waitSignal(cell.pin_requested) as signal:
        qtbot.mouseClick(cell.pin_button, Qt.MouseButton.LeftButton)
    assert signal.args == [7, True]


def test_table_emits_record_ids_not_row_numbers(qtbot):
    table = ApplicationTableWidget()
    qtbot.addWidget(table)
    table.set_application_ids([40, 10, 30])
    with qtbot.waitSignal(table.rows_reordered) as signal:
        table.apply_row_move(0, 2)
    assert signal.args == [[10, 30, 40]]
```

- [ ] **Step 2: Run widget tests and verify failure**

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest tests\test_application_table.py tests\test_ui_widgets.py -q
```

Expected: missing table class and pin signal fail.

- [ ] **Step 3: Implement the table component**

Configure:

```python
self.setDragEnabled(True)
self.setAcceptDrops(True)
self.setDropIndicatorShown(True)
self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
```

Maintain `_application_ids: list[int]`. Override `dropEvent` to calculate source and destination,
move the ID, call the base visual move or refresh safely, and emit a copied ID list only after a
valid move. Expose `apply_row_move(source_row, destination_row)` so behavior is testable without
native mouse-drag timing.

- [ ] **Step 4: Add pin action**

Change the constructor to:

```python
def __init__(
    self,
    application_id: int,
    is_pinned: bool,
    parent: QWidget | None = None,
) -> None:
```

Store `self.pin_button`, label it `取消置顶` or `置顶`, and emit the requested target boolean.
Keep edit, history, and delete signals unchanged.

- [ ] **Step 5: Run tests and commit**

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest tests\test_application_table.py tests\test_ui_widgets.py -q
git add recruitment_ledger/ui/application_table.py recruitment_ledger/ui/widgets.py tests/test_application_table.py tests/test_ui_widgets.py
git commit -m "feat: add draggable application table"
```

### Task 5: Main-window sort, drag, pin, and settings integration

**Files:**
- Modify: `recruitment_ledger/ui/main_window.py`
- Modify: `recruitment_ledger/styles.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `SortMode`, `ApplicationTableWidget`, and Task 3 service methods
- Produces: `MainWindow.sort_mode_combo`
- Persists: `table/sort_mode`

- [ ] **Step 1: Write failing UI integration tests**

```python
def test_window_exposes_three_sort_modes(window):
    assert [
        window.sort_mode_combo.itemText(index)
        for index in range(window.sort_mode_combo.count())
    ] == ["手动排序", "按投递时间", "按最后更新时间"]


def test_drag_in_updated_mode_switches_to_manual(window, monkeypatch):
    calls: list[tuple[list[int], SortMode]] = []
    monkeypatch.setattr(window.service, "reorder_visible", lambda ids, mode: calls.append((ids, mode)))
    window.sort_mode_combo.setCurrentText("按最后更新时间")

    window._rows_reordered([2, 1])

    assert window.sort_mode_combo.currentText() == "手动排序"
    assert calls == [([2, 1], SortMode.UPDATED_AT)]


def test_pin_action_does_not_touch_business_timestamp(window, service):
    record = window._records[0]
    previous = record.updated_at
    window._set_pinned(record.id, True)
    assert service.get(record.id).updated_at == previous
```

- [ ] **Step 2: Run smoke tests and verify failure**

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest tests\test_ui_smoke.py -q
```

Expected: missing combo, handlers, and draggable table assertions fail.

- [ ] **Step 3: Add sort-mode UI and settings**

Map labels to enum values:

```python
SORT_MODE_LABELS = {
    "手动排序": SortMode.MANUAL,
    "按投递时间": SortMode.APPLICATION_DATE,
    "按最后更新时间": SortMode.UPDATED_AT,
}
```

Insert `sort_mode_combo` in the toolbar. Restore `table/sort_mode`, accepting only enum values and
falling back to `SortMode.UPDATED_AT`. Save the current enum value in `closeEvent`.

- [ ] **Step 4: Replace the table and pass current sort mode**

Instantiate `ApplicationTableWidget`, connect `rows_reordered`, and load with:

```python
self._records = self.service.list(
    self.search_edit.text().strip(),
    status,
    self._current_sort_mode(),
)
self.table.set_application_ids(
    [record.id for record in self._records if record.id is not None]
)
```

After an automatic-mode drag, call `reorder_visible(ids, previous_mode)`, switch the combo to
manual without double-refresh, and refresh. On failure, show a Chinese error and reload from the
database.

- [ ] **Step 5: Wire pinning and visible marker**

Construct `ActionCell(record.id, record.is_pinned)`, connect `pin_requested` to `_set_pinned`, and
prefix the company display with `📌 ` for pinned records while keeping the underlying model value
unchanged. On success refresh; on failure show a Chinese error and reload.

- [ ] **Step 6: Verify CSV order and run focused tests**

The existing export method must continue passing `self._records` directly so export order matches
the screen and internal fields remain absent from `export.py` headers.

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest tests\test_ui_smoke.py tests\test_export.py tests\test_application_table.py tests\test_ui_widgets.py -q
git diff --check
```

Expected: all focused tests pass.

- [ ] **Step 7: Commit**

```powershell
git add recruitment_ledger/ui/main_window.py recruitment_ledger/styles.py tests/test_ui_smoke.py
git commit -m "feat: integrate sorting and pinning controls"
```

### Task 6: Full verification, local installation, package, and GitHub v1.1.2 release

**Files:**
- Modify: `README.md` only if verified behavior needs correction
- Create outside Git: `C:\Users\wty\Documents\Codex\2026-07-30\jie\outputs\Recruitment-Record-Ledger-Windows-x64.zip`
- Create outside Git: `C:\Users\wty\Documents\Codex\2026-07-30\jie\outputs\Recruitment-Record-Ledger-Windows-x64.zip.sha256`
- Publish: GitHub `main` and Release `v1.1.2`

**Interfaces:**
- Consumes: completed rename/migration and ordering/pinning plans
- Produces: tested local installation and public v1.1.2 Release

- [ ] **Step 1: Run all automated quality gates**

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q recruitment_ledger
git diff --check
git status --short
```

Expected: all tests pass, compilation succeeds, no whitespace errors, and no unexplained changes.

- [ ] **Step 2: Run the active-name audit**

```powershell
rg -n "秋招进程台账|autumn-recruitment-ledger|from autumn_ledger|import autumn_ledger" `
  main.py recruitment_ledger tests scripts README.md AGENTS.md
```

Expected: only explicitly asserted legacy migration/cleanup fixtures remain. Separately verify
that `autumn_recruitment.db` remains in paths, migration tests, and README.

- [ ] **Step 3: Build and inspect Windows output**

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ".\招聘记录台账.spec"
```

Verify:

- `dist\招聘记录台账\招聘记录台账.exe` exists;
- `_internal` contains the Python runtime;
- no `.db`, backup, export, log, source, test, `.git`, or `.venv` content is present;
- EXE icon matches `assets\ui.ico`.

- [ ] **Step 4: Run local sync and interactive smoke checks**

Run the local sync script with its launch check. Verify the installed EXE at
`%LOCALAPPDATA%\Programs\RecruitmentRecordLedger\招聘记录台账.exe`, the desktop shortcut,
window title, `版本v1.1.2`, all three sort modes, drag persistence after restart, pin persistence,
time sorting, edit/history/delete/export, and “检查更新”. Verify the old program install and old
shortcut are removed only after success.

- [ ] **Step 5: Create and verify the minimal ZIP**

Stage exactly the complete `dist\招聘记录台账` directory plus a UTF-8 `使用说明.txt`, compress it
to:

`C:\Users\wty\Documents\Codex\2026-07-30\jie\outputs\Recruitment-Record-Ledger-Windows-x64.zip`

Enumerate the ZIP, verify expected root/EXE/runtime and forbidden-content rules, calculate SHA-256,
then extract into a fresh path containing Chinese characters and spaces and launch the extracted
EXE. Confirm its database is created only under the disposable user-data path.

- [ ] **Step 6: Commit any verified documentation correction**

If verification changes README, run the relevant command again and commit:

```powershell
git add README.md
git commit -m "docs: finalize v1.1.2 usage"
```

Do not create an empty commit when no correction is needed.

- [ ] **Step 7: Push main**

```powershell
git status --short
git push origin main
```

Expected: clean worktree and successful push to
`wangtianyu-0403/Recruitment-Record-Ledger`.

- [ ] **Step 8: Create the v1.1.2 Release**

Use GitHub CLI to create a non-draft, non-prerelease `v1.1.2` Release targeting `main`, title it
`招聘记录台账 v1.1.2`, describe the one-time manual upgrade and automatic data migration, and
upload the ZIP plus SHA-256 file.

- [ ] **Step 9: Verify the published release**

Confirm through GitHub CLI/API:

- tag and target commit match pushed `main`;
- Release is public, non-draft, and non-prerelease;
- exact asset name and byte size match the local ZIP;
- downloaded asset SHA-256 equals the local digest;
- latest-release lookup returns `v1.1.2`;
- release updater parsing accepts the published metadata.
