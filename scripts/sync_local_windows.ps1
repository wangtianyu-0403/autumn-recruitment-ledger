[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\AutumnRecruitmentLedger"),
    [string]$DesktopDir = [Environment]::GetFolderPath("Desktop"),
    [string]$SourceDist = "",
    [switch]$SkipBuild,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

try {
    if (-not $SkipBuild) {
        if (-not (Test-Path -LiteralPath $python)) {
            py -3 -m venv (Join-Path $repoRoot ".venv")
            if ($LASTEXITCODE -ne 0) {
                throw "创建 Python 虚拟环境失败。"
            }
        }

        & $python -m pip install -r (Join-Path $repoRoot "requirements-dev.txt")
        if ($LASTEXITCODE -ne 0) {
            throw "安装开发依赖失败。"
        }

        $previousQtPlatform = $env:QT_QPA_PLATFORM
        try {
            $env:QT_QPA_PLATFORM = "offscreen"
            & $python -m pytest -q
            if ($LASTEXITCODE -ne 0) {
                throw "自动测试失败，已停止本地同步。"
            }
        }
        finally {
            $env:QT_QPA_PLATFORM = $previousQtPlatform
        }

        Push-Location $repoRoot
        try {
            & $python -m PyInstaller --noconfirm --clean --onedir --windowed `
                --icon ".\assets\ui.ico" --name "秋招进程台账" ".\main.py"
            if ($LASTEXITCODE -ne 0) {
                throw "PyInstaller 打包失败。"
            }
        }
        finally {
            Pop-Location
        }
        $SourceDist = Join-Path $repoRoot "dist\秋招进程台账"
    }

    if ([string]::IsNullOrWhiteSpace($SourceDist)) {
        throw "未提供待安装的发布目录。"
    }

    $source = (Resolve-Path -LiteralPath $SourceDist).Path
    $sourceExe = Join-Path $source "秋招进程台账.exe"
    $sourceRuntimes = @(
        Get-ChildItem -File -LiteralPath (Join-Path $source "_internal") `
            -Filter "python3*.dll" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^python3\d+\.dll$" }
    )
    if (-not (Test-Path -LiteralPath $sourceExe)) {
        throw "发布目录缺少秋招进程台账.exe。"
    }
    if ($sourceRuntimes.Count -eq 0) {
        throw "发布目录缺少 _internal\python3NN.dll。"
    }

    $InstallDir = [IO.Path]::GetFullPath($InstallDir)
    $DesktopDir = [IO.Path]::GetFullPath($DesktopDir)
    $installParent = Split-Path -Parent $InstallDir
    $installLeaf = Split-Path -Leaf $InstallDir
    $installedExe = Join-Path $InstallDir "秋招进程台账.exe"

    if (Test-Path -LiteralPath $installedExe) {
        $running = @(
            Get-CimInstance Win32_Process -Filter "Name = '秋招进程台账.exe'" `
                -ErrorAction SilentlyContinue |
                Where-Object { $_.ExecutablePath -eq $installedExe }
        )
        if ($running.Count -gt 0) {
            throw "本地程序正在运行。请先关闭程序，再重新执行同步。"
        }
    }

    New-Item -ItemType Directory -Force -Path $installParent, $DesktopDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $staging = Join-Path $installParent "$installLeaf.staging-$stamp"
    $backup = Join-Path $installParent "$installLeaf.backup-$stamp"
    $failed = Join-Path $installParent "$installLeaf.failed-$stamp"
    Copy-Item -Recurse -LiteralPath $source -Destination $staging

    if (-not (Test-Path -LiteralPath (Join-Path $staging "秋招进程台账.exe"))) {
        throw "临时安装目录缺少秋招进程台账.exe。"
    }
    $stagingRuntimes = @(
        Get-ChildItem -File -LiteralPath (Join-Path $staging "_internal") `
            -Filter "python3*.dll" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^python3\d+\.dll$" }
    )
    if ($stagingRuntimes.Count -eq 0) {
        throw "临时安装目录缺少 _internal\python3NN.dll。"
    }

    $backupCreated = $false
    try {
        if (Test-Path -LiteralPath $InstallDir) {
            Move-Item -LiteralPath $InstallDir -Destination $backup
            $backupCreated = $true
        }
        Move-Item -LiteralPath $staging -Destination $InstallDir
    }
    catch {
        if ($backupCreated) {
            if (Test-Path -LiteralPath $InstallDir) {
                Move-Item -LiteralPath $InstallDir -Destination $failed
            }
            if (Test-Path -LiteralPath $backup) {
                Move-Item -LiteralPath $backup -Destination $InstallDir
            }
        }
        throw
    }

    $shortcutPath = Join-Path $DesktopDir "秋招进程台账.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $InstallDir "秋招进程台账.exe"
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.IconLocation = "$($shortcut.TargetPath),0"
    $shortcut.Save()

    if (-not $NoLaunch) {
        Start-Process -FilePath $shortcut.TargetPath -WorkingDirectory $InstallDir
    }

    Write-Host ""
    Write-Host "本地程序同步完成：$InstallDir"
    Write-Host "桌面快捷方式：$shortcutPath"
    if ($backupCreated) {
        Write-Host "旧版本备份：$backup"
    }
    exit 0
}
catch {
    Write-Error "本地同步失败：$($_.Exception.Message)"
    exit 1
}
