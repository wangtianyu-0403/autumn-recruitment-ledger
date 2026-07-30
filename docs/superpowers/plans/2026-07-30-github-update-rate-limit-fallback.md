# GitHub Update Rate-Limit Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish v1.1.1 so manual update checks continue securely when GitHub's unauthenticated REST API returns a 403 or 429 rate-limit response.

**Architecture:** Preserve the REST API as the primary metadata source. Add a narrowly scoped GitHub web fallback that follows the public latest-release redirect, parses the exact Windows asset and digest from the expanded-assets HTML, returns the existing `ReleaseInfo`, and leaves download/install verification unchanged.

**Tech Stack:** Python 3.13+, standard-library `urllib`, `html.parser`, pytest, PySide6, PyInstaller

## Global Constraints

- Set `APP_VERSION` exactly to `1.1.1`, push GitHub `main`, and create a public `v1.1.1` GitHub Release.
- Trigger the web fallback only for API `HTTP 403` or `HTTP 429`.
- Do not add GitHub tokens, credentials, dependencies, automatic checks, retries, or background network traffic.
- Require HTTPS, exact `github.com` host, exact repository path, exact tag path, exact Windows asset name, and a valid SHA-256 digest.
- Preserve the existing `ReleaseInfo`, download digest verification, ZIP validation, updater rollback, database paths, and UI flow.

---

## File Structure

- `autumn_ledger/update.py`: owns both update metadata transports, shared metadata validation, and the rate-limit fallback decision.
- `tests/test_update.py`: verifies Release HTML parsing, security rejection, and API-to-web fallback behavior.
- `autumn_ledger/constants.py`: application version changes from `1.1.0` to `1.1.1`.
- `tests/test_ui_smoke.py`: verifies the visible version label is `版本v1.1.1`.
- `scripts/sync_local_windows.ps1`: existing build/install entry point, unchanged.

### Task 1: Parse GitHub Release HTML into trusted metadata

**Files:**
- Modify: `tests/test_update.py`
- Modify: `autumn_ledger/update.py:3-115`

**Interfaces:**
- Consumes: final latest-release URL and expanded-assets HTML.
- Produces: `_parse_web_release(final_url: str, assets_html: str) -> ReleaseInfo`.
- Produces: `_validate_asset_digest(value: object) -> str`.

- [ ] **Step 1: Write the failing valid-HTML test**

Add imports:

```python
from autumn_ledger.update import (
    WINDOWS_ASSET_NAME,
    _parse_web_release,
)
```

Add a literal HTML fixture and test:

```python
def _expanded_assets_html(
    *,
    asset_name: str = WINDOWS_ASSET_NAME,
    digest: str = "sha256:" + "b" * 64,
) -> str:
    return f"""
    <a href="/wangtianyu-0403/autumn-recruitment-ledger/releases/download/v1.2.0/{asset_name}">
      <span>{asset_name}</span>
    </a>
    <clipboard-copy
      aria-label="Copy to clipboard digest for {asset_name}"
      value="{digest}">
    </clipboard-copy>
    """


def test_parse_web_release_reads_exact_asset_and_digest() -> None:
    release = _parse_web_release(
        "https://github.com/wangtianyu-0403/"
        "autumn-recruitment-ledger/releases/tag/v1.2.0",
        _expanded_assets_html(),
    )

    assert release == ReleaseInfo(
        version=(1, 2, 0),
        tag_name="v1.2.0",
        asset_url=(
            "https://github.com/wangtianyu-0403/autumn-recruitment-ledger/"
            "releases/download/v1.2.0/"
            "autumn-recruitment-ledger-Windows-x64.zip"
        ),
        asset_digest="sha256:" + "b" * 64,
        html_url=(
            "https://github.com/wangtianyu-0403/"
            "autumn-recruitment-ledger/releases/tag/v1.2.0"
        ),
    )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_update.py::test_parse_web_release_reads_exact_asset_and_digest -q
```

Expected: collection fails because `_parse_web_release` does not exist.

- [ ] **Step 3: Add security rejection tests**

```python
@pytest.mark.parametrize(
    "final_url",
    [
        "http://github.com/wangtianyu-0403/autumn-recruitment-ledger/releases/tag/v1.2.0",
        "https://example.com/wangtianyu-0403/autumn-recruitment-ledger/releases/tag/v1.2.0",
        "https://github.com/other/repository/releases/tag/v1.2.0",
    ],
)
def test_parse_web_release_rejects_untrusted_latest_url(final_url: str) -> None:
    with pytest.raises(UpdateError, match="Release"):
        _parse_web_release(final_url, _expanded_assets_html())


@pytest.mark.parametrize(
    ("asset_name", "digest"),
    [
        ("wrong.zip", "sha256:" + "b" * 64),
        (WINDOWS_ASSET_NAME, ""),
        (WINDOWS_ASSET_NAME, "sha256:not-a-digest"),
    ],
)
def test_parse_web_release_rejects_invalid_asset_metadata(
    asset_name: str,
    digest: str,
) -> None:
    with pytest.raises(UpdateError):
        _parse_web_release(
            "https://github.com/wangtianyu-0403/"
            "autumn-recruitment-ledger/releases/tag/v1.2.0",
            _expanded_assets_html(asset_name=asset_name, digest=digest),
        )
```

- [ ] **Step 4: Implement the HTML parser and shared digest validation**

Add imports and constants:

```python
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlsplit

GITHUB_WEB_ORIGIN = "https://github.com"
REPOSITORY_WEB_PATH = "/wangtianyu-0403/autumn-recruitment-ledger"
LATEST_RELEASE_WEB = f"{GITHUB_WEB_ORIGIN}{REPOSITORY_WEB_PATH}/releases/latest"
EXPANDED_ASSETS_WEB = (
    f"{GITHUB_WEB_ORIGIN}{REPOSITORY_WEB_PATH}/releases/expanded_assets/{{tag}}"
)
```

Implement:

```python
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
```

Replace the duplicated REST API digest validation with
`_validate_asset_digest(asset.get("digest"))`.

- [ ] **Step 5: Run parser tests and verify GREEN**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_update.py -k "parse_web_release or fetch_latest_release" -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the trusted HTML parser**

```powershell
git add autumn_ledger/update.py tests/test_update.py
git commit -m "feat: parse trusted GitHub release metadata"
```

### Task 2: Fall back only when the API is rate-limited

**Files:**
- Modify: `tests/test_update.py`
- Modify: `autumn_ledger/update.py`

**Interfaces:**
- Consumes: `HTTPError.code`, `LATEST_RELEASE_WEB`, `EXPANDED_ASSETS_WEB`.
- Produces: `_fetch_latest_release_from_web(timeout: float = 10.0) -> ReleaseInfo`.
- Preserves: `fetch_latest_release(api_url: str = ..., timeout: float = 10.0) -> ReleaseInfo`.

- [ ] **Step 1: Write failing 403/429 fallback tests**

Import the module for narrow monkeypatching:

```python
from email.message import Message
from urllib.error import HTTPError

from autumn_ledger import update
```

Add:

```python
@pytest.mark.parametrize("status_code", [403, 429])
def test_fetch_latest_release_falls_back_for_rate_limits(
    monkeypatch,
    status_code: int,
) -> None:
    expected = ReleaseInfo(
        version=(1, 2, 0),
        tag_name="v1.2.0",
        asset_url="https://github.com/example/update.zip",
        asset_digest="sha256:" + "c" * 64,
        html_url="https://github.com/example/releases/tag/v1.2.0",
    )

    def raise_rate_limit(*args, **kwargs):
        raise HTTPError(
            url="https://api.github.com/example",
            code=status_code,
            msg="rate limit exceeded",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr(update, "urlopen", raise_rate_limit)
    monkeypatch.setattr(
        update,
        "_fetch_latest_release_from_web",
        lambda timeout=10.0: expected,
    )

    assert fetch_latest_release() == expected
```

- [ ] **Step 2: Write the non-rate-limit rejection test**

```python
def test_fetch_latest_release_does_not_fallback_for_other_http_errors(
    monkeypatch,
) -> None:
    def raise_server_error(*args, **kwargs):
        raise HTTPError(
            url="https://api.github.com/example",
            code=500,
            msg="server error",
            hdrs=Message(),
            fp=None,
        )

    def unexpected_fallback(*args, **kwargs):
        raise AssertionError("web fallback must not run")

    monkeypatch.setattr(update, "urlopen", raise_server_error)
    monkeypatch.setattr(
        update,
        "_fetch_latest_release_from_web",
        unexpected_fallback,
        raising=False,
    )

    with pytest.raises(UpdateError, match="GitHub"):
        fetch_latest_release()
```

- [ ] **Step 3: Run fallback tests and verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_update.py -k "rate_limit or other_http" -q
```

Expected: 403/429 cases fail because `fetch_latest_release()` currently
wraps every `HTTPError` immediately.

- [ ] **Step 4: Implement the web transport**

```python
def _fetch_latest_release_from_web(timeout: float = 10.0) -> ReleaseInfo:
    latest_request = Request(
        LATEST_RELEASE_WEB,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urlopen(latest_request, timeout=timeout) as response:
            final_url = response.geturl()

        tag_prefix = f"{REPOSITORY_WEB_PATH}/releases/tag/"
        parsed = urlsplit(final_url)
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
    except (
        HTTPError,
        URLError,
        OSError,
        UnicodeDecodeError,
    ) as exc:
        raise UpdateError(f"无法读取备用 GitHub Release 信息：{exc}") from exc

    return _parse_web_release(final_url, assets_html)
```

Split the API JSON parsing into
`_release_from_api_payload(payload: object) -> ReleaseInfo`, then update
`fetch_latest_release()`:

```python
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

return _release_from_api_payload(payload)
```

- [ ] **Step 5: Run update tests and verify GREEN**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_update.py -q
```

Expected: all update tests pass.

- [ ] **Step 6: Commit the rate-limit fallback**

```powershell
git add autumn_ledger/update.py tests/test_update.py
git commit -m "fix: fall back when GitHub API is rate limited"
```

### Task 3: Bump v1.1.1, verify, synchronize, and publish

**Files:**
- Verify: `autumn_ledger/constants.py`
- Modify: `autumn_ledger/constants.py`
- Modify: `tests/test_ui_smoke.py`
- Verify: `tests/`
- Build/install through: `scripts/sync_local_windows.ps1`

**Interfaces:**
- Consumes: real public GitHub API and Release pages.
- Produces: locally installed v1.1.1 executable, pushed `main`, and public v1.1.1 Release.

- [ ] **Step 1: Run the complete test suite**

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Write the failing visible-version test**

Change the existing assertion in `tests/test_ui_smoke.py`:

```python
assert window.version_label.text() == "版本v1.1.1"
```

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_ui_smoke.py::test_main_window_contains_required_controls -q
```

Expected: FAIL because the application still displays `版本v1.1.0`.

- [ ] **Step 3: Bump the application version**

Update `autumn_ledger/constants.py`:

```python
APP_VERSION = "1.1.1"
```

Run the focused UI test again and expect `1 passed`.

- [ ] **Step 4: Verify the real exhausted-limit fallback before publication**

While the GitHub API returns `403 rate limit exceeded`, run:

```powershell
.\.venv\Scripts\python.exe -c "from autumn_ledger.update import fetch_latest_release; r=fetch_latest_release(); print(r.tag_name, r.asset_digest, r.asset_url)"
```

Expected before publication:

- command exits with code 0;
- tag is `v1.1.0`;
- digest is
  `sha256:921fe238b72cdf0c54ca4ca6cdffdddfeb71ce9d888650f9b4c209a662e57835`;
- asset URL ends with
  `autumn-recruitment-ledger-Windows-x64.zip`.

- [ ] **Step 5: Commit v1.1.1 and run the full suite**

```powershell
git add autumn_ledger/constants.py tests/test_ui_smoke.py
git commit -m "release: prepare v1.1.1"
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Rebuild and synchronize the stable local application**

```powershell
.\scripts\sync_local_windows.ps1 -NoLaunch
```

Expected: tests and PyInstaller succeed, the stable installation under
`%LOCALAPPDATA%\Programs\AutumnRecruitmentLedger` is replaced, and the
desktop shortcut remains valid.

- [ ] **Step 7: Build and audit the minimum release ZIP**

Compress the exact `dist\秋招进程台账` directory into:

```text
C:\Users\wty\Documents\Codex\2026-07-30\jie\work\release-v1.1.1\autumn-recruitment-ledger-Windows-x64.zip
```

Verify:

- archive passes `validate_update_archive()`;
- archive contains no `.git`, `.venv`, `__pycache__`, database, log, backup,
  or user-data files;
- compute and record SHA-256 and byte size.

- [ ] **Step 8: Verify the installed executable and shortcut**

Compare the SHA-256 of the built and installed executables, then verify
the desktop shortcut target is exactly:

```text
C:\Users\wty\AppData\Local\Programs\AutumnRecruitmentLedger\秋招进程台账.exe
```

- [ ] **Step 9: Merge, push, and publish v1.1.1**

After a fresh full test run, fast-forward local `main`, push `main`, and
create GitHub Release `v1.1.1` with the audited ASCII-named ZIP asset.
Release notes must describe the 403/429 fallback and include the exact
SHA-256.

- [ ] **Step 10: Verify the remote release and live updater**

Verify through `gh api` and direct download:

- tag is `v1.1.1`, target is `main`, draft and prerelease are false;
- exactly one ZIP asset exists with the expected name, size, and digest;
- direct asset download returns HTTP 200;
- remote `main` equals local `main`;
- while the unauthenticated API remains limited, `fetch_latest_release()`
  returns `v1.1.1` through the web fallback.

- [ ] **Step 11: Run final repository checks**

```powershell
git diff --check
git status --short
```

Expected: no uncommitted source changes.
