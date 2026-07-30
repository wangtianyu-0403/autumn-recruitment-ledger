# Windows Portable ZIP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a single Windows x64 ZIP whose extracted `秋招进程台账.exe` runs without Python and stores persistent data only in the recipient's local Windows profile.

**Architecture:** Rebuild the existing PyInstaller `onedir` target from the committed spec, stage the complete `dist/秋招进程台账` directory with a short usage guide, and compress that directory into one ZIP. Validate the executable under an isolated application-data environment, then extract the ZIP into a path containing Chinese characters and spaces for a final end-to-end launch check.

**Tech Stack:** Python 3.13 virtual environment, PySide6, PyInstaller `onedir`, pytest, PowerShell `Compress-Archive`, Windows process inspection.

## Global Constraints

- Target Windows 10/11 64-bit.
- Recipients must not need Python, administrator rights, registry changes, or an installer.
- Distribution must not contain developer databases, logs, backups, exports, caches, source files, tests, or `build` intermediates.
- Persistent data must remain under `QStandardPaths.AppDataLocation` for the current Windows user.
- The deliverable must be named `秋招进程台账-Windows-x64.zip`.
- Reliability takes priority over single-EXE packaging or unsafe dependency removal.

---

### Task 1: Clean Build and Test

**Files:**
- Read: `秋招进程台账.spec`
- Recreate: `build/秋招进程台账/`
- Recreate: `dist/秋招进程台账/`

**Interfaces:**
- Consumes: `.venv/Scripts/python.exe`, `秋招进程台账.spec`
- Produces: `dist/秋招进程台账/秋招进程台账.exe` and its `_internal` runtime directory

- [ ] **Step 1: Run the complete automated test suite**

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: exit code `0` and `24 passed`.

- [ ] **Step 2: Remove only the named PyInstaller target directories**

Resolve and verify that both targets are children of the repository before removal:

```powershell
$repo = (Resolve-Path .).Path
$buildTarget = Join-Path $repo 'build\秋招进程台账'
$distTarget = Join-Path $repo 'dist\秋招进程台账'
@($buildTarget, $distTarget) | ForEach-Object {
    if (-not $_.StartsWith($repo + '\')) { throw "Unsafe target: $_" }
    if (Test-Path -LiteralPath $_) { Remove-Item -Recurse -Force -LiteralPath $_ }
}
```

- [ ] **Step 3: Build the production target**

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm .\秋招进程台账.spec
```

Expected: exit code `0`; both `dist/秋招进程台账/秋招进程台账.exe` and `dist/秋招进程台账/_internal/python313.dll` exist.

- [ ] **Step 4: Record the build file count and uncompressed size**

```powershell
$files = Get-ChildItem -Recurse -File -LiteralPath '.\dist\秋招进程台账'
[pscustomobject]@{
    FileCount = $files.Count
    SizeMB = [math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 2)
}
```

Expected: non-zero file count and size.

### Task 2: Isolated Local Persistence Verification

**Files:**
- Read: `autumn_ledger/paths.py`
- Exercise: `dist/秋招进程台账/秋招进程台账.exe`
- Create temporarily: a directory under `%TEMP%`

**Interfaces:**
- Consumes: rebuilt executable
- Produces: evidence that startup creates and reuses a database outside the program directory

- [ ] **Step 1: Create an isolated Windows application-data environment**

```powershell
$isolatedRoot = Join-Path $env:TEMP ('ledger-package-test-' + [guid]::NewGuid())
$isolatedAppData = Join-Path $isolatedRoot 'Roaming'
$isolatedLocalData = Join-Path $isolatedRoot 'Local'
New-Item -ItemType Directory -Force -Path $isolatedAppData, $isolatedLocalData | Out-Null
$env:APPDATA = $isolatedAppData
$env:LOCALAPPDATA = $isolatedLocalData
```

- [ ] **Step 2: Launch the executable and verify the first startup**

Start `dist/秋招进程台账/秋招进程台账.exe`, wait up to 15 seconds for a non-zero main-window handle and title `秋招进程台账`, record that it is responding, then close only that process.

Expected: visible responding window and a newly created `ledger.db` somewhere under `$isolatedRoot`.

- [ ] **Step 3: Verify that no database was written beside the executable**

```powershell
Get-ChildItem -Recurse -File -LiteralPath '.\dist\秋招进程台账' -Filter '*.db'
```

Expected: no output.

- [ ] **Step 4: Launch a second time against the same isolated environment**

Record the database path, length, and last-write time; launch and close the executable again using the same `APPDATA` and `LOCALAPPDATA` values; confirm the same database still exists and remains a valid SQLite database.

Expected: the identical database path is reused, proving local memory persists across restarts.

- [ ] **Step 5: Remove only the verified temporary isolation directory**

Resolve `$isolatedRoot`, verify it starts with the resolved `%TEMP%` path plus a separator and its leaf starts with `ledger-package-test-`, then remove it recursively.

### Task 3: Stage and Compress the Distribution

**Files:**
- Read: `dist/秋招进程台账/**`
- Create: `C:/Users/wty/Documents/Codex/2026-07-30/jie/outputs/秋招进程台账/使用说明.txt`
- Create: `C:/Users/wty/Documents/Codex/2026-07-30/jie/outputs/秋招进程台账-Windows-x64.zip`

**Interfaces:**
- Consumes: verified production `dist` directory
- Produces: one portable ZIP and a usage guide inside it

- [ ] **Step 1: Prepare the output staging directory**

Resolve the exact `outputs/秋招进程台账` directory, remove only that directory if it already exists, recreate it, and copy the complete contents of `dist/秋招进程台账` into it.

- [ ] **Step 2: Add the end-user usage guide**

Create `使用说明.txt` with UTF-8 BOM and this content:

```text
秋招进程台账（Windows 10/11 64 位）

使用方法：
1. 请先完整解压 ZIP 压缩包。
2. 打开“秋招进程台账”文件夹。
3. 双击“秋招进程台账.exe”运行。
4. 请勿删除或移动“_internal”文件夹。

数据说明：
- 台账数据只保存在当前用户自己的 Windows 本地应用数据目录。
- 数据不会上传，也不会与其他电脑自动同步。
- 更新程序时，请先使用程序内的备份功能保存重要数据。
```

- [ ] **Step 3: Audit staged content before compression**

Recursively reject staged files matching `*.db`, `*.sqlite`, `*.sqlite3`, `*.log`, `*.bak`, `*.py`, `*.pyc`, `*.spec`, `*.toc`, `*.pkg`, `*.html`, or directory names `build`, `tests`, `__pycache__`.

Expected: no rejected paths.

- [ ] **Step 4: Create the ZIP**

```powershell
Compress-Archive -LiteralPath 'C:\Users\wty\Documents\Codex\2026-07-30\jie\outputs\秋招进程台账' `
    -DestinationPath 'C:\Users\wty\Documents\Codex\2026-07-30\jie\outputs\秋招进程台账-Windows-x64.zip' `
    -CompressionLevel Optimal -Force
```

Expected: ZIP exists and is smaller than the uncompressed directory.

### Task 4: Extracted-Package End-to-End Verification

**Files:**
- Read: `outputs/秋招进程台账-Windows-x64.zip`
- Create temporarily: `%TEMP%/台账 发布验证 <guid>/`

**Interfaces:**
- Consumes: final ZIP
- Produces: launch evidence, privacy audit evidence, final size, and SHA-256

- [ ] **Step 1: List and audit ZIP entries**

Use `System.IO.Compression.ZipFile` to enumerate all entries. Confirm the archive contains `秋招进程台账/秋招进程台账.exe`, `_internal/python313.dll`, and `使用说明.txt`; reject the same private/source/build patterns from Task 3.

- [ ] **Step 2: Extract to a path containing Chinese characters and a space**

```powershell
$extractRoot = Join-Path $env:TEMP ('台账 发布验证 ' + [guid]::NewGuid())
Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot
```

- [ ] **Step 3: Launch the extracted executable**

Start `$extractRoot/秋招进程台账/秋招进程台账.exe`, wait up to 15 seconds for a responding main window titled `秋招进程台账`, verify the executable path is inside `$extractRoot`, then close only that process.

Expected: launch verification passes.

- [ ] **Step 4: Remove the verified extraction directory**

Resolve `$extractRoot`, verify its parent is the resolved `%TEMP%` directory and its leaf starts with `台账 发布验证 `, then remove it recursively.

- [ ] **Step 5: Generate final artifact metadata**

```powershell
Get-Item -LiteralPath $zipPath | Select-Object FullName, Length, LastWriteTime
Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath
```

Expected: one ZIP path, non-zero length, and a 64-character SHA-256 hash.

- [ ] **Step 6: Confirm repository cleanliness**

```powershell
git status --short --branch
```

Expected: no uncommitted changes from packaging; `build`, `dist`, and user data remain ignored.
