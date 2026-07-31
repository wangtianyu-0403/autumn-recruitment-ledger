from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

LATEST_RELEASE_API = (
    "https://api.github.com/repos/"
    "wangtianyu-0403/autumn-recruitment-ledger/releases/latest"
)
WINDOWS_ASSET_NAME = "autumn-recruitment-ledger-Windows-x64.zip"
GITHUB_WEB_ORIGIN = "https://github.com"
REPOSITORY_WEB_PATH = "/wangtianyu-0403/autumn-recruitment-ledger"
LATEST_RELEASE_WEB = f"{GITHUB_WEB_ORIGIN}{REPOSITORY_WEB_PATH}/releases/latest"
EXPANDED_ASSETS_WEB = (
    f"{GITHUB_WEB_ORIGIN}{REPOSITORY_WEB_PATH}/releases/expanded_assets/{{tag}}"
)
USER_AGENT = "RecruitmentRecordLedger-Updater"
UPDATE_ROOT_NAME = "招聘记录台账"
UPDATE_EXECUTABLE_NAME = "招聘记录台账.exe"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: tuple[int, int, int]
    tag_name: str
    asset_url: str
    asset_digest: str
    html_url: str


def parse_version(value: str) -> tuple[int, int, int]:
    normalized = value.removeprefix("v")
    parts = normalized.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise UpdateError(f"无法识别版本号：{value or '空值'}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _validate_asset_digest(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != len("sha256:") + 64
    ):
        raise UpdateError("Windows 更新包缺少有效的 SHA-256 校验值。")
    try:
        int(value.removeprefix("sha256:"), 16)
    except ValueError as exc:
        raise UpdateError("Windows 更新包的 SHA-256 校验值无效。") from exc
    return value.lower()


class _ExpandedAssetsParser(HTMLParser):
    def __init__(self, tag_name: str) -> None:
        super().__init__()
        encoded_tag = quote(tag_name, safe="")
        self.expected_href = (
            f"{REPOSITORY_WEB_PATH}/releases/download/{encoded_tag}/"
            f"{WINDOWS_ASSET_NAME}"
        )
        self.asset_href: str | None = None
        self.asset_digest: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href") == self.expected_href:
            self.asset_href = self.expected_href
        if (
            tag == "clipboard-copy"
            and values.get("aria-label")
            == f"Copy to clipboard digest for {WINDOWS_ASSET_NAME}"
        ):
            self.asset_digest = values.get("value")


def _parse_web_release(final_url: str, assets_html: str) -> ReleaseInfo:
    parsed = urlsplit(final_url)
    tag_prefix = f"{REPOSITORY_WEB_PATH}/releases/tag/"
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not parsed.path.startswith(tag_prefix)
    ):
        raise UpdateError("GitHub Release 跳转地址无效。")

    encoded_tag = parsed.path.removeprefix(tag_prefix)
    if not encoded_tag or "/" in encoded_tag:
        raise UpdateError("GitHub Release 版本地址无效。")
    tag_name = unquote(encoded_tag)
    version = parse_version(tag_name)

    parser = _ExpandedAssetsParser(tag_name)
    parser.feed(assets_html)
    if parser.asset_href is None:
        raise UpdateError(f"最新版本中未找到 Windows 更新包：{WINDOWS_ASSET_NAME}")
    asset_digest = _validate_asset_digest(parser.asset_digest)

    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        asset_url=urljoin(GITHUB_WEB_ORIGIN, parser.asset_href),
        asset_digest=asset_digest,
        html_url=final_url,
    )


def _fetch_latest_release_from_web(timeout: float = 10.0) -> ReleaseInfo:
    latest_request = Request(
        LATEST_RELEASE_WEB,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urlopen(latest_request, timeout=timeout) as response:
            final_url = response.geturl()

        parsed = urlsplit(final_url)
        tag_prefix = f"{REPOSITORY_WEB_PATH}/releases/tag/"
        if (
            parsed.scheme != "https"
            or parsed.netloc != "github.com"
            or not parsed.path.startswith(tag_prefix)
        ):
            raise UpdateError("GitHub Release 跳转地址无效。")
        encoded_tag = parsed.path.removeprefix(tag_prefix)
        if not encoded_tag or "/" in encoded_tag:
            raise UpdateError("GitHub Release 版本地址无效。")

        assets_url = EXPANDED_ASSETS_WEB.format(tag=encoded_tag)
        assets_request = Request(
            assets_url,
            headers={"User-Agent": USER_AGENT},
        )
        with urlopen(assets_request, timeout=timeout) as response:
            assets_html = response.read().decode("utf-8")
    except UpdateError:
        raise
    except (HTTPError, URLError, OSError, UnicodeDecodeError) as exc:
        raise UpdateError(f"无法读取备用 GitHub Release 信息：{exc}") from exc

    return _parse_web_release(final_url, assets_html)


def fetch_latest_release(
    api_url: str = LATEST_RELEASE_API,
    timeout: float = 10.0,
) -> ReleaseInfo:
    request = Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {403, 429}:
            try:
                return _fetch_latest_release_from_web(timeout)
            except UpdateError as fallback_error:
                raise UpdateError(
                    "GitHub API 请求受限，且备用 Release 信息读取失败："
                    f"{fallback_error}"
                ) from fallback_error
        raise UpdateError(f"无法读取 GitHub 更新信息：{exc}") from exc
    except (URLError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError(f"无法读取 GitHub 更新信息：{exc}") from exc

    if not isinstance(payload, dict):
        raise UpdateError("GitHub 更新信息格式无效。")
    if payload.get("draft") is True or payload.get("prerelease") is True:
        raise UpdateError("GitHub 最新版本不是正式发布版本。")

    tag_name = payload.get("tag_name")
    html_url = payload.get("html_url")
    assets = payload.get("assets")
    if not isinstance(tag_name, str) or not isinstance(html_url, str):
        raise UpdateError("GitHub 更新信息缺少版本或发布地址。")
    if not isinstance(assets, list):
        raise UpdateError("GitHub 更新信息缺少附件列表。")

    asset = next(
        (
            candidate
            for candidate in assets
            if isinstance(candidate, dict)
            and candidate.get("name") == WINDOWS_ASSET_NAME
        ),
        None,
    )
    if asset is None:
        raise UpdateError(f"最新版本中未找到 Windows 更新包：{WINDOWS_ASSET_NAME}")

    asset_url = asset.get("browser_download_url")
    asset_digest = asset.get("digest")
    if not isinstance(asset_url, str) or not asset_url:
        raise UpdateError("Windows 更新包缺少下载地址。")
    validated_digest = _validate_asset_digest(asset_digest)

    return ReleaseInfo(
        version=parse_version(tag_name),
        tag_name=tag_name,
        asset_url=asset_url,
        asset_digest=validated_digest,
        html_url=html_url,
    )


def download_release_asset(
    release: ReleaseInfo,
    destination: Path,
    progress: Callable[[int, int], None] | None = None,
    timeout: float = 60.0,
) -> Path:
    resolved = destination.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    partial = resolved.with_suffix(f"{resolved.suffix}.part")
    partial.unlink(missing_ok=True)
    request = Request(
        release.asset_url,
        headers={"User-Agent": USER_AGENT},
    )
    digest = sha256()
    downloaded = 0
    try:
        with urlopen(request, timeout=timeout) as response, partial.open("wb") as output:
            total_header = response.headers.get("Content-Length")
            total = int(total_header) if total_header and total_header.isdigit() else 0
            while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress(downloaded, total)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"下载更新包失败：{exc}") from exc

    expected = release.asset_digest.removeprefix("sha256:").lower()
    if digest.hexdigest().lower() != expected:
        partial.unlink(missing_ok=True)
        raise UpdateError("更新包 SHA-256 校验失败，已拒绝安装。")
    partial.replace(resolved)
    return resolved


def validate_update_archive(archive_path: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            normalized_names: set[str] = set()
            for info in archive.infolist():
                normalized = info.filename.replace("\\", "/")
                member = PurePosixPath(normalized)
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or (member.parts and member.parts[0].endswith(":"))
                ):
                    raise UpdateError(f"更新包包含不安全路径：{info.filename}")
                normalized_names.add(normalized.rstrip("/"))
    except (OSError, zipfile.BadZipFile) as exc:
        raise UpdateError(f"无法读取更新包：{exc}") from exc

    if f"{UPDATE_ROOT_NAME}/{UPDATE_EXECUTABLE_NAME}" not in normalized_names:
        raise UpdateError("更新包缺少主程序。")
    runtime_pattern = re.compile(
        rf"^{re.escape(UPDATE_ROOT_NAME)}/_internal/python3\d+\.dll$",
        re.IGNORECASE,
    )
    if not any(runtime_pattern.fullmatch(name) for name in normalized_names):
        raise UpdateError("更新包缺少 Python 运行时。")


UPDATER_SCRIPT = r"""param(
    [int]$ProcessId,
    [Parameter(Mandatory=$true)][string]$ArchivePath,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [Parameter(Mandatory=$true)][string]$ExecutableName,
    [Parameter(Mandatory=$true)][string]$LogPath,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"

function Write-UpdateLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value "[$timestamp] $Message"
}

$parent = Split-Path -Parent $InstallDir
$leaf = Split-Path -Leaf $InstallDir
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$staging = Join-Path $parent "$leaf.staging-$stamp"
$backup = Join-Path $parent "$leaf.backup-$stamp"
$failed = Join-Path $parent "$leaf.failed-$stamp"

try {
    Write-UpdateLog "等待旧程序退出。"
    if ($ProcessId -gt 0) {
        Wait-Process -Id $ProcessId -ErrorAction SilentlyContinue
    }

    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $staging
    $newRoot = Join-Path $staging "招聘记录台账"
    $newExe = Join-Path $newRoot $ExecutableName
    $newRuntimes = @(
        Get-ChildItem -File -LiteralPath (Join-Path $newRoot "_internal") `
            -Filter "python3*.dll" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^python3\d+\.dll$" }
    )
    if (-not (Test-Path -LiteralPath $newExe)) {
        throw "更新包缺少主程序。"
    }
    if ($newRuntimes.Count -eq 0) {
        throw "更新包缺少 Python 运行时。"
    }

    if (Test-Path -LiteralPath $InstallDir) {
        Move-Item -LiteralPath $InstallDir -Destination $backup
    }
    Move-Item -LiteralPath $newRoot -Destination $InstallDir

    if (-not $NoRestart) {
        Start-Process -FilePath (Join-Path $InstallDir $ExecutableName) `
            -WorkingDirectory $InstallDir
    }
    Write-UpdateLog "更新完成。旧版本备份：$backup"
    exit 0
}
catch {
    Write-UpdateLog "更新失败：$($_.Exception.Message)"
    if (Test-Path -LiteralPath $InstallDir) {
        Move-Item -LiteralPath $InstallDir -Destination $failed
    }
    if (Test-Path -LiteralPath $backup) {
        Move-Item -LiteralPath $backup -Destination $InstallDir
        Write-UpdateLog "已恢复旧版本。"
    }
    exit 1
}
"""


def write_updater_script(script_path: Path) -> Path:
    resolved = script_path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(UPDATER_SCRIPT, encoding="utf-8-sig")
    return resolved


def launch_updater(
    archive_path: Path,
    install_dir: Path,
    executable_path: Path,
) -> Path:
    validate_update_archive(archive_path)
    update_dir = Path(tempfile.mkdtemp(prefix="recruitment-ledger-update-"))
    script_path = write_updater_script(update_dir / "apply-update.ps1")
    log_path = update_dir / "update.log"
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-ProcessId",
        str(sys.getpid()),
        "-ArchivePath",
        str(archive_path.resolve()),
        "-InstallDir",
        str(install_dir.resolve()),
        "-ExecutableName",
        executable_path.name,
        "-LogPath",
        str(log_path),
    ]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            command,
            cwd=update_dir,
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError as exc:
        raise UpdateError(f"无法启动更新助手：{exc}") from exc
    return log_path
