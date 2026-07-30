# Embed Windows Application Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed the user-provided `ui.ico` into every Windows EXE build, synchronize the local v1.1.1 installation, and safely replace the existing v1.1.1 GitHub Release ZIP.

**Architecture:** Store the icon inside the repository so packaging is reproducible, pass the same icon to both PyInstaller entry points, and keep the shortcut bound to icon index 0 of the installed EXE. Verify the result through a real build and PE resource inspection rather than source-text-only tests.

**Tech Stack:** Windows ICO, PyInstaller, PowerShell, batch, Python `struct`, `pefile`, pytest, GitHub CLI

## Global Constraints

- Keep `APP_VERSION` exactly `1.1.1`.
- Use `E:\Users\wty\Desktop\ui.ico` unchanged; do not redraw or upscale it.
- Store the repository copy at `assets/ui.ico`.
- Do not modify application runtime behavior, data paths, update logic, database, or non-Windows build scripts.
- Do not move, delete, or force-rewrite Git tag `v1.1.1`.
- Push `main` and replace only the Windows ZIP asset and release notes in the existing public v1.1.1 Release.
- Preserve a local backup of the previous v1.1.1 ZIP before replacement.

---

## File Structure

- `assets/ui.ico`: repository-owned copy of the Windows application icon.
- `scripts/build_windows.bat`: normal Windows package command.
- `scripts/sync_local_windows.ps1`: tested local build, install, and shortcut command.
- `README.md`: documents the repository icon and the 16×16 source limitation.
- `docs/superpowers/specs/2026-07-30-embed-windows-app-icon-design.md`: approved design.

### Task 1: Add the icon asset to both Windows build paths

**Files:**
- Create: `assets/ui.ico`
- Modify: `scripts/build_windows.bat`
- Modify: `scripts/sync_local_windows.ps1`
- Modify: `README.md`

**Interfaces:**
- Consumes: `assets/ui.ico`.
- Produces: PyInstaller invocations with `--icon` pointing to that file.
- Preserves: `scripts\sync_local_windows.bat` and the existing shortcut `IconLocation`.

- [ ] **Step 1: Copy and verify the ICO asset**

Create `assets` and copy the binary without transformation:

```powershell
New-Item -ItemType Directory -Path .\assets
Copy-Item -LiteralPath 'E:\Users\wty\Desktop\ui.ico' `
    -Destination '.\assets\ui.ico'
```

Verify source and repository hashes match, then parse the ICO header:

```python
import struct
from hashlib import sha256
from pathlib import Path

source = Path(r"E:\Users\wty\Desktop\ui.ico").read_bytes()
stored = Path("assets/ui.ico").read_bytes()
assert sha256(source).digest() == sha256(stored).digest()
reserved, kind, count = struct.unpack_from("<HHH", stored, 0)
assert (reserved, kind, count) == (0, 1, 1)
width, height, _, _, _, bpp, size, offset = struct.unpack_from(
    "<BBBBHHII", stored, 6
)
assert (width, height, bpp, size, offset) == (16, 16, 24, 872, 22)
```

- [ ] **Step 2: Add the icon to the batch build**

Update the PyInstaller command in `scripts/build_windows.bat`:

```bat
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --icon "assets\ui.ico" --name "秋招进程台账" main.py
```

- [ ] **Step 3: Add the icon to local synchronization builds**

Update the PyInstaller command in `scripts/sync_local_windows.ps1`:

```powershell
& $python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --icon ".\assets\ui.ico" --name "秋招进程台账" ".\main.py"
```

- [ ] **Step 4: Verify PowerShell syntax**

```powershell
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path '.\scripts\sync_local_windows.ps1'),
    [ref]$tokens,
    [ref]$errors
) | Out-Null
if ($errors.Count -ne 0) { throw ($errors | Out-String) }
```

Expected: zero parse errors.

- [ ] **Step 5: Document the icon source**

Add a concise README note that Windows builds use `assets/ui.ico`, and
that the supplied source currently contains only a 16×16 layer.

- [ ] **Step 6: Commit the build configuration**

```powershell
git add assets/ui.ico scripts/build_windows.bat `
    scripts/sync_local_windows.ps1 README.md
git commit -m "build: embed Windows application icon"
```

### Task 2: Build and prove the icon is embedded

**Files:**
- Verify: `assets/ui.ico`
- Verify: `dist/秋招进程台账/秋招进程台账.exe`
- Build/install through: `scripts/sync_local_windows.ps1`

**Interfaces:**
- Consumes: the repository icon and both updated packaging parameters.
- Produces: installed v1.1.1 EXE with `RT_ICON` and `RT_GROUP_ICON`.

- [ ] **Step 1: Run the complete test suite**

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Gracefully close the installed app if running**

Resolve only the exact installed executable process:

```text
C:\Users\wty\AppData\Local\Programs\AutumnRecruitmentLedger\秋招进程台账.exe
```

Request a normal window close and stop if it does not exit within ten
seconds; do not force-kill it.

- [ ] **Step 3: Build and synchronize**

```powershell
.\scripts\sync_local_windows.ps1 -NoLaunch
```

Expected: tests pass, PyInstaller reports that it copies the icon to the
EXE, and local synchronization succeeds.

- [ ] **Step 4: Inspect PE icon resources**

Use the installed `pefile` package to verify resource types and the exact
ICO image payload:

```python
import struct
from pathlib import Path

import pefile

icon = Path("assets/ui.ico").read_bytes()
_, _, count = struct.unpack_from("<HHH", icon, 0)
assert count == 1
_, _, _, _, _, _, size, offset = struct.unpack_from("<BBBBHHII", icon, 6)
expected_payload = icon[offset : offset + size]

exe_path = Path(r"dist\秋招进程台账\秋招进程台账.exe")
pe = pefile.PE(str(exe_path))
resource_types = {
    entry.id: entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries
}
assert 3 in resource_types       # RT_ICON
assert 14 in resource_types      # RT_GROUP_ICON

icon_payloads = []
for name_entry in resource_types[3].directory.entries:
    for language_entry in name_entry.directory.entries:
        data = language_entry.data.struct
        icon_payloads.append(pe.get_data(data.OffsetToData, data.Size))
assert expected_payload in icon_payloads
```

- [ ] **Step 5: Verify installation and shortcut**

- Built and installed EXE SHA-256 values must match.
- Desktop shortcut target must equal the installed EXE.
- Shortcut `IconLocation` must equal the installed EXE plus `,0`.
- The application version must remain `1.1.1`.

### Task 3: Replace the v1.1.1 GitHub asset without rewriting the tag

**Files:**
- Generate: `C:\Users\wty\Documents\Codex\2026-07-30\jie\work\release-v1.1.1-icon\autumn-recruitment-ledger-Windows-x64.zip`
- Update: `C:\Users\wty\Documents\Codex\2026-07-30\jie\work\release-notes-v1.1.1-icon.md`
- Replace output: `C:\Users\wty\Documents\Codex\2026-07-30\jie\outputs\秋招进程台账-Windows-x64.zip`

**Interfaces:**
- Consumes: verified `dist\秋招进程台账`.
- Produces: pushed `main` and one audited Windows asset on Release `v1.1.1`.

- [ ] **Step 1: Build and audit the minimum ZIP**

Compress the exact `dist\秋招进程台账` directory. Verify:

- `validate_update_archive()` accepts it;
- it contains the EXE and `python3NN.dll`;
- it contains no `.git`, `.venv`, `__pycache__`, database, log, backup,
  export, or user-data files;
- record exact byte size and SHA-256.

- [ ] **Step 2: Preserve the old public asset**

Download the current Release asset to:

```text
C:\Users\wty\Documents\Codex\2026-07-30\jie\work\v1.1.1-before-icon\autumn-recruitment-ledger-Windows-x64.zip
```

Verify its digest against GitHub before modifying the Release.

- [ ] **Step 3: Prepare updated release notes**

Retain the v1.1.1 rate-limit fix notes, add the embedded application icon,
and replace the SHA-256 with the new ZIP digest.

- [ ] **Step 4: Run final source verification**

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

Expected: all tests pass and the source tree is clean.

- [ ] **Step 5: Merge and push `main`**

Fast-forward local `main`, rerun the full suite on merged `main`, and push
it to `origin/main`. Record the existing `v1.1.1` tag commit before any
Release asset operations.

- [ ] **Step 6: Upload the replacement under a temporary asset name**

Copy the new ZIP to
`autumn-recruitment-ledger-Windows-x64-icon-refresh.zip`, upload it to
Release `v1.1.1`, and verify its GitHub digest before deleting anything.

- [ ] **Step 7: Replace the old asset safely**

Using exact GitHub asset IDs:

1. delete only the old `autumn-recruitment-ledger-Windows-x64.zip`;
2. rename the verified temporary asset to
   `autumn-recruitment-ledger-Windows-x64.zip`;
3. update the Release notes.

If temporary upload or digest verification fails, stop and leave the old
asset untouched.

- [ ] **Step 8: Verify remote and local delivery**

- Release remains `v1.1.1`, non-draft, and non-prerelease.
- Exactly one Windows ZIP asset remains with the expected name, size, and
  digest.
- Direct download returns HTTP 200.
- Git tag `v1.1.1` still points to the commit recorded before replacement.
- Remote `main` equals local `main`.
- Local output ZIP equals the Release asset.
