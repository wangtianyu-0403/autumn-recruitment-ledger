# 招聘记录台账

招聘记录台账是一个离线、单机使用的招聘投递管理桌面程序。招聘记录只保存在本机 SQLite 数据库中，不需要登录，不提供云同步，也不会自动上传业务数据。

项目仓库：<https://github.com/wangtianyu-0403/Recruitment-Record-Ledger>

## 功能

- 新增、编辑、搜索和按状态筛选岗位
- 在首页直接修改进度，并自动记录完整状态历史
- 统计全部岗位、已投递、面试进行中和已有 Offer
- 公司官网一键调用系统默认浏览器
- 软删除、回收站恢复和二次确认永久删除
- 导出当前筛选结果为带 UTF-8 BOM 的 CSV
- 每日自动备份、手动一致性备份和安全恢复
- 保存窗口位置、尺寸、状态筛选和表格列宽
- 日志滚动写入本地应用数据目录

截图可放在仓库的 `docs/screenshots/` 目录；程序运行不依赖截图或在线资源。

## Windows 免安装版

Windows 10/11 64 位用户可在 [Releases](https://github.com/wangtianyu-0403/Recruitment-Record-Ledger/releases) 下载 `Recruitment-Record-Ledger-Windows-x64.zip`。

1. 完整解压 ZIP。
2. 打开“招聘记录台账”文件夹。
3. 双击 `招聘记录台账.exe`。

免安装版无需安装 Python。Windows EXE 使用仓库中的 `assets/ui.ico`。

### 从 v1.1.1 一次性手动升级到 v1.1.2

v1.1.1 的“检查更新”仍查询旧发布位置，因此升级到 v1.1.2 必须手动完成一次：

1. 退出正在运行的 v1.1.1。
2. 从新仓库 Releases 页面下载 `Recruitment-Record-Ledger-Windows-x64.zip`。
3. 将 ZIP 完整解压到新的程序目录，不要把压缩包内容混入旧程序目录。
4. 运行新目录中的 `招聘记录台账.exe`。
5. 在程序中确认既有记录可见，再按需保留或删除旧程序文件。

首次启动 v1.1.2 时，如果新数据目录尚无数据库而旧目录
`%APPDATA%\PersonalTools\AutumnRecruitmentLedger\` 中存在数据库，程序会使用 SQLite backup API 将已提交数据复制到新目录，并执行完整性检查。已有的新数据库绝不会被覆盖；旧数据目录会原样保留作为回退副本。旧 `backups/` 和 `exports/` 中尚未存在于新目录的文件也会复制，旧日志不会迁移。迁移失败时新数据库不会生效，旧数据仍保留。

数据库文件名保持为 `data/autumn_recruitment.db`，仅应用数据根目录更名。

### v1.1.2 之后的“检查更新”

- 只有点击工具栏中的“检查更新”才会连接 GitHub；程序启动时不会自动联网。
- 程序查询新仓库的最新正式版本；GitHub API 返回 403/429 时会改用公开 Release 页面。
- 检测到新版本后先询问，确认后才下载 `Recruitment-Record-Ledger-Windows-x64.zip`。
- 更新包必须通过 GitHub SHA-256 校验和 ZIP 安全检查。
- 外部更新助手会备份当前程序目录、安装并启动新的 `招聘记录台账.exe`；失败时恢复旧程序。
- 更新器只操作程序安装目录，不修改本地台账数据库。

### 开发电脑一键同步

修改代码后双击：

```text
scripts\sync_local_windows.bat
```

脚本会安装开发依赖、运行完整测试、重新打包，并将程序原子同步到：

```text
%LOCALAPPDATA%\Programs\RecruitmentRecordLedger\
```

同步脚本验证新 `招聘记录台账.exe` 后创建或修复桌面快捷方式 `招聘记录台账.lnk`。新程序安装并通过启动测试后，脚本才清理 v1.1.1 的旧本地安装目录和旧快捷方式；使用测试参数 `-NoLaunch` 跳过启动验证时不会清理旧目标。当前程序或待清理的 v1.1.1 仍在运行时，脚本会在写入前停止；测试失败、启动失败或发布目录不完整时也会保留旧目标。

## 环境要求

- Python 3.10 或更高版本
- Windows 10/11、macOS 或主流 Linux 桌面环境

本项目已在 Windows、Python 3.14.6 和 PySide6 6.11.1 下完成测试与打包验证。依赖范围保留为 `PySide6>=6.8,<7`。

## 安装和启动

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

macOS/Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Windows 也可以双击 `scripts\run_windows.bat`。macOS/Linux 可运行：

```bash
./scripts/run_unix.sh
```

## 开发依赖和测试

Windows：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m pytest -q
```

macOS/Linux：

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

测试数据库和测试目录均由 pytest 在临时目录中创建，不会访问真实用户数据。

## 数据位置

程序通过 `QStandardPaths.AppDataLocation` 确定目录，不依赖源码目录。启动前设置组织名 `PersonalTools` 和应用名 `RecruitmentRecordLedger`。

Windows 上的数据根目录为：

```text
%APPDATA%\PersonalTools\RecruitmentRecordLedger\
```

其他操作系统和 Qt 配置会映射到各自的标准应用数据位置，应以程序内“打开数据目录”按钮打开的位置为准。目录内容：

```text
data/autumn_recruitment.db
backups/
exports/
logs/recruitment_ledger.log
```

业务数据只保存在 SQLite 数据库中。QSettings 只保存窗口和筛选等界面设置。

## CSV 导出

“导出 CSV”导出当前搜索和状态筛选结果。默认目录为 `exports/`，也可以在保存窗口中选择其他位置。文件使用 `utf-8-sig`，字段中的逗号、换行和双引号由 Python `csv` 模块正确转义。

## 备份和恢复

程序每天首次启动时创建一份 `autumn_recruitment_YYYYMMDD.db`，自动备份最多保留最近 30 份。手动备份和自动备份均使用 SQLite backup API。

恢复时会先验证 SQLite 完整性和 `applications` 表，再提示确认，并在替换前生成 `pre_restore_*.db` 安全备份。恢复后连接会自动重建并刷新界面。

## 打包

Windows 双击或在终端执行：

```powershell
scripts\build_windows.bat
```

脚本安装开发依赖、运行完整测试，然后使用 PyInstaller
`--onedir --windowed --icon assets\ui.ico --name "招聘记录台账"` 打包。产物位于：

```text
dist\招聘记录台账\招聘记录台账.exe
```

macOS/Linux：

```bash
./scripts/build_unix.sh
```

PyInstaller 产物不能跨操作系统使用，每个平台必须在对应操作系统上分别构建。

## 常见问题

- 无法启动：确认 Python 版本不低于 3.10，并重新运行一键启动脚本。
- 官网按钮不可用：该记录尚未填写公司官网；编辑记录并填写有效的 HTTP/HTTPS 地址。
- CSV 在 Excel 中乱码：请确认打开的是程序导出的原文件，导出文件已包含 UTF-8 BOM。
- 恢复被拒绝：备份必须是可正常打开、完整且包含 `applications` 表的 SQLite 数据库。
- 数据目录不可写：检查当前账户对系统应用数据目录的写权限。

## 卸载

删除源码目录或 PyInstaller 产物即可卸载程序，不会自动删除招聘数据。需要保留数据时保留应用数据目录；需要完整清除时，先退出程序，再删除“打开数据目录”所显示的整个目录。界面设置可在系统对应的 Qt `QSettings` 存储位置清除。

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
