# Compact Statistic Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vertically stretched dashboard statistics with four compact, equal-width cards while keeping application version `v1.1.0`.

**Architecture:** Keep `MainWindow` and the existing horizontal four-card layout unchanged. Constrain each `StatisticCard` at the widget boundary, place all surplus vertical space below its labels, and fix the application stylesheet selector so it targets the actual card widget type.

**Tech Stack:** Python 3.13+, PySide6, pytest, pytest-qt, Qt offscreen rendering, PyInstaller

## Global Constraints

- Keep `APP_VERSION` exactly `1.1.0`; do not create a GitHub Release.
- Do not change database schemas, data paths, statistics calculations, updater behavior, or toolbar controls.
- Keep four equal-width cards in one horizontal row at the existing minimum window width.
- Use a fixed card height of `90px`, margins `(16, 12, 16, 12)`, and label spacing `4px`.
- Local installation must continue to use `%LOCALAPPDATA%\Programs\AutumnRecruitmentLedger`.

---

## File Structure

- `autumn_ledger/ui/widgets.py`: owns `StatisticCard` sizing and its internal title/value layout.
- `autumn_ledger/styles.py`: owns the white card background, border, and corner styling.
- `tests/test_ui_widgets.py`: directly verifies card geometry and the stylesheet selector.
- `docs/superpowers/specs/2026-07-30-compact-statistic-cards-design.md`: approved behavior and visual constraints.

### Task 1: Constrain the statistic card geometry

**Files:**
- Create: `tests/test_ui_widgets.py`
- Modify: `autumn_ledger/ui/widgets.py:3-24`

**Interfaces:**
- Consumes: `StatisticCard(title: str, parent: QWidget | None = None)`
- Produces: the same public constructor and `set_value(value: int) -> None`; only geometry and layout policy change.

- [ ] **Step 1: Write the failing geometry test**

```python
from PySide6.QtWidgets import QSizePolicy

from autumn_ledger.ui.widgets import StatisticCard


def test_statistic_card_uses_compact_fixed_geometry(qtbot) -> None:
    card = StatisticCard("全部岗位")
    qtbot.addWidget(card)

    margins = card.layout().contentsMargins()
    assert card.minimumHeight() == 90
    assert card.maximumHeight() == 90
    assert card.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert card.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        16,
        12,
        16,
        12,
    )
    assert card.layout().spacing() == 4
    assert card.layout().stretch(card.layout().count() - 1) == 1
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_ui_widgets.py::test_statistic_card_uses_compact_fixed_geometry -q
```

Expected: FAIL because the current card has no fixed height, uses margins `(14, 10, 14, 10)`, and has no trailing stretch.

- [ ] **Step 3: Implement the compact card boundary**

Update the imports and constructor:

```python
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class StatisticCard(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setFixedHeight(90)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #667085; font-size: 13px;")
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #274C6B;"
        )
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_ui_widgets.py::test_statistic_card_uses_compact_fixed_geometry -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit the geometry change**

```powershell
git add tests/test_ui_widgets.py autumn_ledger/ui/widgets.py
git commit -m "style: compact dashboard statistic cards"
```

### Task 2: Apply the intended card surface style

**Files:**
- Modify: `tests/test_ui_widgets.py`
- Modify: `autumn_ledger/styles.py:69-74`

**Interfaces:**
- Consumes: `StatisticCard` dynamic property `card=True`
- Produces: `APP_STYLESHEET` rule `QWidget[card="true"]`

- [ ] **Step 1: Write the failing stylesheet test**

Append:

```python
from autumn_ledger.styles import APP_STYLESHEET


def test_stylesheet_targets_statistic_card_widgets() -> None:
    assert 'QWidget[card="true"]' in APP_STYLESHEET
    assert 'QLabel[card="true"]' not in APP_STYLESHEET
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_widgets.py::test_stylesheet_targets_statistic_card_widgets -q
```

Expected: FAIL because the current selector is `QLabel[card="true"]`.

- [ ] **Step 3: Fix the stylesheet selector**

Change only the selector:

```css
QWidget[card="true"] {
    background: #FFFFFF;
    border: 1px solid #E0E5EA;
    border-radius: 8px;
}
```

Do not retain the old `padding: 12px`; internal spacing is owned by the
`StatisticCard` layout.

- [ ] **Step 4: Run the widget tests and verify GREEN**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_ui_widgets.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the surface styling**

```powershell
git add tests/test_ui_widgets.py autumn_ledger/styles.py
git commit -m "style: apply statistic card surfaces"
```

### Task 3: Verify the rendered interface and synchronize the local app

**Files:**
- Verify: `autumn_ledger/constants.py`
- Verify: `tests/`
- Generate temporarily: `work/compact-stat-cards.png`
- Build and install through: `scripts/sync_local_windows.ps1`

**Interfaces:**
- Consumes: `MainWindow`, `APP_STYLESHEET`, `scripts/sync_local_windows.ps1`
- Produces: a verified local v1.1.0 executable and repaired desktop shortcut; no repository source changes.

- [ ] **Step 1: Verify the version remains unchanged**

Run:

```powershell
rg -n 'APP_VERSION = "1.1.0"' autumn_ledger/constants.py
```

Expected: one match.

- [ ] **Step 2: Run the complete test suite**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Render an offscreen screenshot**

Run a temporary Python verification script that constructs `MainWindow`,
applies `APP_STYLESHEET`, resizes it to `1200x760`, processes Qt events,
and saves `work/compact-stat-cards.png`.

```python
import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from autumn_ledger.backup import BackupManager
from autumn_ledger.database import Database
from autumn_ledger.paths import AppPaths
from autumn_ledger.repository import ApplicationRepository
from autumn_ledger.services import ApplicationService
from autumn_ledger.styles import APP_STYLESHEET
from autumn_ledger.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
app.setStyleSheet(APP_STYLESHEET)
with TemporaryDirectory() as temporary:
    paths = AppPaths.from_root(Path(temporary))
    paths.ensure_directories()
    database = Database(paths.database_path)
    database.initialize()
    service = ApplicationService(ApplicationRepository(database))
    window = MainWindow(service, BackupManager(database, paths), paths)
    window.resize(1200, 760)
    window.show()
    app.processEvents()
    Path("work").mkdir(exist_ok=True)
    assert window.grab().save("work/compact-stat-cards.png")
    window.close()
    database.close()
```

- [ ] **Step 4: Inspect the screenshot**

Confirm:

- all four white cards are equal width;
- each title sits directly above its number;
- the card row is about `90px` high;
- the table or empty-state area begins below the card row;
- the bottom-right text remains `版本v1.1.0`.

- [ ] **Step 5: Rebuild and synchronize the stable local application**

Run:

```powershell
.\scripts\sync_local_windows.ps1 -NoLaunch
```

Expected: tests pass, PyInstaller succeeds, the stable installation is
updated under `%LOCALAPPDATA%\Programs\AutumnRecruitmentLedger`, and the
desktop shortcut remains valid.

- [ ] **Step 6: Verify repository cleanliness**

Run:

```powershell
git diff --check
git status --short
```

Expected: no uncommitted source changes; temporary screenshots remain
outside the committed source set.
