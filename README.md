# 秋招进程台账

一个离线、单机使用的秋招投递管理桌面程序。招聘记录保存在本机 SQLite 数据库中，支持状态历史、搜索筛选、回收站、CSV 导出以及数据库备份和恢复。

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

截图可放在仓库的 `docs/screenshots/` 目录；当前版本不依赖截图或联网资源运行。

## Windows 免安装版

Windows 10/11 64 位用户可在 [Releases](https://github.com/wangtianyu-0403/autumn-recruitment-ledger/releases) 下载 `秋招进程台账-Windows-x64.zip`。

1. 完整解压 ZIP。
2. 打开“秋招进程台账”文件夹。
3. 双击 `秋招进程台账.exe`。

免安装版无需安装 Python。数据库只保存在当前 Windows 用户的 `%APPDATA%\PersonalTools\AutumnRecruitmentLedger\`，不会包含在 ZIP 中，也不会自动上传。

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

Windows 也可以双击 `scripts\run_windows.bat`。脚本会自动创建 `.venv`、安装运行依赖并启动程序。macOS/Linux 可运行：

```bash
./scripts/run_unix.sh
```

VS Code 用户在集成终端进入项目根目录后，选择 `.venv` 解释器，执行 `python main.py` 即可。

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

程序通过 `QStandardPaths.AppDataLocation` 确定目录，不依赖源码目录。启动前设置组织名 `PersonalTools` 和应用名 `AutumnRecruitmentLedger`。

本机 Windows 实测路径为：

```text
%APPDATA%\PersonalTools\AutumnRecruitmentLedger\
```

其他操作系统和 Qt 配置会映射到各自的标准应用数据位置，应以程序内“打开数据目录”按钮打开的位置为准。目录内容：

```text
data/autumn_recruitment.db
backups/
exports/
logs/autumn_ledger.log
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

脚本安装开发依赖、运行完整测试，然后使用 PyInstaller `--onedir --windowed` 打包。产物位于：

```text
dist\秋招进程台账\秋招进程台账.exe
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
