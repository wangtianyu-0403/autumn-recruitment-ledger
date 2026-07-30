from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LATEST_RELEASE_API = (
    "https://api.github.com/repos/"
    "wangtianyu-0403/autumn-recruitment-ledger/releases/latest"
)
WINDOWS_ASSET_NAME = "autumn-recruitment-ledger-Windows-x64.zip"
USER_AGENT = "AutumnRecruitmentLedger-Updater"


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
    except (HTTPError, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
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
    if (
        not isinstance(asset_digest, str)
        or not asset_digest.startswith("sha256:")
        or len(asset_digest) != len("sha256:") + 64
    ):
        raise UpdateError("Windows 更新包缺少有效的 SHA-256 校验值。")
    try:
        int(asset_digest.removeprefix("sha256:"), 16)
    except ValueError as exc:
        raise UpdateError("Windows 更新包的 SHA-256 校验值无效。") from exc

    return ReleaseInfo(
        version=parse_version(tag_name),
        tag_name=tag_name,
        asset_url=asset_url,
        asset_digest=asset_digest.lower(),
        html_url=html_url,
    )
