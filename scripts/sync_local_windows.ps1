[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\RecruitmentRecordLedger"),
    [string]$DesktopDir = [Environment]::GetFolderPath("Desktop"),
    [string]$SourceDist = "",
    [switch]$SkipBuild,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

function Get-ProcessesAtExecutablePath {
    param(
        [Parameter(Mandatory = $true)][string]$ExecutablePath,
        [Parameter(Mandatory = $true)][string]$ExecutableName
    )

    $escapedName = $ExecutableName.Replace("'", "''")
    try {
        $candidates = @(
            Get-CimInstance Win32_Process -Filter "Name = '$escapedName'" `
                -ErrorAction Stop
        )
    }
    catch {
        throw "无法查询进程 [$ExecutableName]，为保护现有安装已停止同步：$($_.Exception.Message)"
    }

    $matches = @()
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate.ExecutablePath)) {
            throw "无法确认进程 [$ExecutableName] 的可执行文件路径，为保护现有安装已停止同步。"
        }
        try {
            $candidatePath = [IO.Path]::GetFullPath($candidate.ExecutablePath)
        }
        catch {
            throw "无法验证进程 [$ExecutableName] 的可执行文件路径，为保护现有安装已停止同步。"
        }
        if ($candidatePath.Equals($ExecutablePath, [StringComparison]::OrdinalIgnoreCase)) {
            $matches += $candidate
        }
    }
    return $matches
}

function Assert-ExecutableNotRunning {
    param(
        [Parameter(Mandatory = $true)][string]$ExecutablePath,
        [Parameter(Mandatory = $true)][string]$ExecutableName,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    $running = @(Get-ProcessesAtExecutablePath `
        -ExecutablePath $ExecutablePath -ExecutableName $ExecutableName)
    if ($running.Count -gt 0) {
        throw $FailureMessage
    }
}

function Wait-ForHealthyMainWindow {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$ExpectedTitle,
        [int]$TimeoutMilliseconds = 5000
    )

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $Process.Refresh()
        if ($Process.HasExited) {
            throw "新程序在健康检查完成前过早退出，退出码：$($Process.ExitCode)。"
        }
        if (
            $Process.MainWindowHandle -ne [IntPtr]::Zero `
            -and $Process.MainWindowTitle -ceq $ExpectedTitle `
            -and $Process.Responding
        ) {
            return
        }
        Start-Sleep -Milliseconds 100
    }

    $Process.Refresh()
    if ($Process.HasExited) {
        throw "新程序在健康检查完成前过早退出，退出码：$($Process.ExitCode)。"
    }
    throw "新程序窗口健康检查失败：未在限定时间内出现标题为 [$ExpectedTitle] 的响应窗口。"
}

function Assert-LaunchedProcessStillHealthy {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$ExecutablePath,
        [Parameter(Mandatory = $true)][string]$ExecutableName,
        [Parameter(Mandatory = $true)][string]$ExpectedTitle
    )

    $matching = @(Get-ProcessesAtExecutablePath `
        -ExecutablePath $ExecutablePath -ExecutableName $ExecutableName)
    if (-not ($matching | Where-Object { $_.ProcessId -eq $Process.Id })) {
        throw "进程查询未确认刚启动的新程序仍从安装目录运行，为保护现有安装已停止同步。"
    }
    $Process.Refresh()
    if ($Process.HasExited) {
        throw "新程序在提交安装前过早退出，退出码：$($Process.ExitCode)。"
    }
    if (
        $Process.MainWindowHandle -eq [IntPtr]::Zero `
        -or $Process.MainWindowTitle -cne $ExpectedTitle `
        -or -not $Process.Responding
    ) {
        throw "新程序窗口在提交安装前未保持可响应状态。"
    }
}

try {
    $InstallDir = [IO.Path]::GetFullPath($InstallDir)
    $DesktopDir = [IO.Path]::GetFullPath($DesktopDir)
    $installParent = Split-Path -Parent $InstallDir
    $installLeaf = Split-Path -Leaf $InstallDir
    $installedExe = Join-Path $InstallDir "招聘记录台账.exe"
    $oldInstall = [IO.Path]::GetFullPath(
        (Join-Path $env:LOCALAPPDATA "Programs\AutumnRecruitmentLedger")
    )
    $oldExe = Join-Path $oldInstall "秋招进程台账.exe"
    $oldShortcut = Join-Path $DesktopDir "秋招进程台账.lnk"

    Assert-ExecutableNotRunning -ExecutablePath $installedExe `
        -ExecutableName "招聘记录台账.exe" `
        -FailureMessage "本地程序正在运行。请先关闭程序，再重新执行同步。"
    Assert-ExecutableNotRunning -ExecutablePath $oldExe `
        -ExecutableName "秋招进程台账.exe" `
        -FailureMessage "旧版程序正在运行。请先关闭程序，再重新执行同步。"

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
                --icon ".\assets\ui.ico" --name "招聘记录台账" ".\main.py"
            if ($LASTEXITCODE -ne 0) {
                throw "PyInstaller 打包失败。"
            }
        }
        finally {
            Pop-Location
        }
        $SourceDist = Join-Path $repoRoot "dist\招聘记录台账"
    }

    if ([string]::IsNullOrWhiteSpace($SourceDist)) {
        throw "未提供待安装的发布目录。"
    }

    $source = (Resolve-Path -LiteralPath $SourceDist).Path
    $sourceExe = Join-Path $source "招聘记录台账.exe"
    $sourceRuntimes = @(
        Get-ChildItem -File -LiteralPath (Join-Path $source "_internal") `
            -Filter "python3*.dll" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^python3\d+\.dll$" }
    )
    if (-not (Test-Path -LiteralPath $sourceExe)) {
        throw "发布目录缺少招聘记录台账.exe。"
    }
    if ($sourceRuntimes.Count -eq 0) {
        throw "发布目录缺少 _internal\python3NN.dll。"
    }

    New-Item -ItemType Directory -Force -Path $installParent, $DesktopDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $staging = Join-Path $installParent "$installLeaf.staging-$stamp"
    $backup = Join-Path $installParent "$installLeaf.backup-$stamp"
    $failed = Join-Path $installParent "$installLeaf.failed-$stamp"
    $shortcutPath = Join-Path $DesktopDir "招聘记录台账.lnk"
    $shortcutBackup = Join-Path $DesktopDir ".招聘记录台账.rollback-$stamp.lnk"
    $backupCreated = $false
    $newInstallActivated = $false
    $shortcutExisted = Test-Path -LiteralPath $shortcutPath -PathType Leaf
    $shortcutBackupCreated = $false
    $launchedProcess = $null
    $launchVerified = $false
    $transactionCommitted = $false
    try {
        if (Test-Path -LiteralPath $shortcutPath) {
            if (-not $shortcutExisted) {
                throw "桌面快捷方式路径不是普通文件，无法安全更新。"
            }
            Copy-Item -Force -LiteralPath $shortcutPath -Destination $shortcutBackup
            $shortcutBackupCreated = $true
        }

        Copy-Item -Recurse -LiteralPath $source -Destination $staging
        if (-not (Test-Path -LiteralPath (Join-Path $staging "招聘记录台账.exe"))) {
            throw "临时安装目录缺少招聘记录台账.exe。"
        }
        $stagingRuntimes = @(
            Get-ChildItem -File -LiteralPath (Join-Path $staging "_internal") `
                -Filter "python3*.dll" -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match "^python3\d+\.dll$" }
        )
        if ($stagingRuntimes.Count -eq 0) {
            throw "临时安装目录缺少 _internal\python3NN.dll。"
        }

        if (Test-Path -LiteralPath $InstallDir) {
            Move-Item -LiteralPath $InstallDir -Destination $backup
            $backupCreated = $true
        }
        Move-Item -LiteralPath $staging -Destination $InstallDir
        $newInstallActivated = $true

        if (-not (Test-Path -LiteralPath $installedExe)) {
            throw "安装目录缺少招聘记录台账.exe。"
        }

        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $installedExe
        $shortcut.WorkingDirectory = $InstallDir
        $shortcut.IconLocation = "$($shortcut.TargetPath),0"
        $shortcut.Save()

        if (-not $NoLaunch) {
            $launchedProcess = Start-Process -FilePath $installedExe `
                -WorkingDirectory $InstallDir -PassThru
            Wait-ForHealthyMainWindow -Process $launchedProcess `
                -ExpectedTitle "招聘记录台账"
            Assert-LaunchedProcessStillHealthy -Process $launchedProcess `
                -ExecutablePath $installedExe `
                -ExecutableName "招聘记录台账.exe" `
                -ExpectedTitle "招聘记录台账"
            Assert-ExecutableNotRunning -ExecutablePath $oldExe `
                -ExecutableName "秋招进程台账.exe" `
                -FailureMessage "旧版程序在提交安装前启动。请先关闭旧版程序，再重新执行同步。"
            $launchVerified = $true
        }

        $transactionCommitted = $true
    }
    catch {
        $transactionError = $_
        if ($null -ne $launchedProcess) {
            $launchedProcess.Refresh()
            if (-not $launchedProcess.HasExited) {
                Stop-Process -Id $launchedProcess.Id -Force -ErrorAction Stop
                if (-not $launchedProcess.WaitForExit(5000)) {
                    throw "无法停止本次同步启动的验证进程，未自动替换现有安装。"
                }
            }
        }
        if ($newInstallActivated -and (Test-Path -LiteralPath $InstallDir)) {
            Move-Item -LiteralPath $InstallDir -Destination $failed
        }
        if ($backupCreated -and (Test-Path -LiteralPath $backup)) {
            Move-Item -LiteralPath $backup -Destination $InstallDir
        }
        if ($shortcutExisted) {
            if ($shortcutBackupCreated) {
                if (Test-Path -LiteralPath $shortcutPath) {
                    Remove-Item -Force -LiteralPath $shortcutPath
                }
                Move-Item -Force -LiteralPath $shortcutBackup -Destination $shortcutPath
                $shortcutBackupCreated = $false
            }
        }
        elseif (Test-Path -LiteralPath $shortcutPath) {
            Remove-Item -Force -LiteralPath $shortcutPath
        }
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -Recurse -Force -LiteralPath $staging
        }
        throw $transactionError
    }

    if (-not $transactionCommitted) {
        throw "本地安装事务未提交。"
    }
    if ($launchVerified) {
        if (
            -not $oldInstall.Equals($InstallDir, [StringComparison]::OrdinalIgnoreCase) `
            -and (Test-Path -LiteralPath $oldInstall)
        ) {
            Remove-Item -Recurse -Force -LiteralPath $oldInstall
        }
        if (Test-Path -LiteralPath $oldShortcut) {
            Remove-Item -Force -LiteralPath $oldShortcut
        }
    }
    else {
        Write-Host "已跳过启动验证，保留旧版安装和快捷方式。"
    }
    if ($shortcutBackupCreated -and (Test-Path -LiteralPath $shortcutBackup)) {
        Remove-Item -Force -LiteralPath $shortcutBackup
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
