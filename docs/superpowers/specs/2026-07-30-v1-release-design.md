# v1.0.0 版本标识与 GitHub 发布设计

## 目标

在“秋招进程台账”主窗口右下角显示固定文字 `版本v1.0.0`，重新构建 Windows 便携 ZIP，并在现有公开仓库 `wangtianyu-0403/autumn-recruitment-ledger` 创建首个 GitHub Release。

## 界面变更

- 在现有 `QStatusBar` 右侧添加永久 `QLabel`。
- 标签文字必须精确为 `版本v1.0.0`。
- 标签使用稳定的对象名 `versionLabel`，便于自动化测试定位。
- 永久标签不受“就绪”“共显示 N 条记录”等临时状态消息影响。
- 版本号由 `autumn_ledger/constants.py` 中的 `APP_VERSION = "1.0.0"` 统一提供，界面使用该常量生成显示文字。

## 测试

- 扩展现有主窗口冒烟测试，断言能够通过对象名找到版本标签。
- 断言版本标签文字等于 `版本v1.0.0`。
- 完整运行 `python -m pytest -q`。
- 重新构建 PyInstaller `onedir` 发布目录，从包含中文和空格的路径启动 EXE，并确认主窗口响应。

## README 更新

- 在现有 `README.md` 增加“Windows 免安装版”章节。
- 提供 GitHub Releases 页面和 `v1.0.0` 发布附件的下载入口。
- 明确说明必须完整解压 ZIP 后运行 `秋招进程台账.exe`。
- 明确说明无需安装 Python，支持 Windows 10/11 64 位。
- 说明数据库保存在当前用户自己的 `%APPDATA%\PersonalTools\AutumnRecruitmentLedger\`，不会随 ZIP 分发或自动上传。

## 构建与发布

- 重新构建 `秋招进程台账-Windows-x64.zip`，替换当前本地输出文件。
- ZIP 只包含程序、PyInstaller 运行时和使用说明，不包含数据库、日志、备份、源码、测试或构建中间文件。
- 将源码、测试、README 和设计文档提交并推送到现有仓库的 `main` 分支。
- 创建标签与 Release `v1.0.0`，标题为 `秋招进程台账 v1.0.0`。
- 将 ZIP 作为 Release 附件上传；不把二进制提交进 Git 历史。
- Release 说明包含系统要求、运行步骤、本地数据行为和 ZIP 的 SHA-256。

## 发布验证

1. 推送前确认完整测试通过。
2. 确认 ZIP 隐私审计没有禁止内容。
3. 确认从 ZIP 解压的 EXE 能显示主窗口并保持响应。
4. 确认远程 `main` 包含 UI 与 README 更新。
5. 确认 GitHub Release 为公开状态，附件名称和大小正确。
6. 从 GitHub API 读取 Release 与附件信息，确认下载链接可用。

## 非目标

- 不制作 MSI 或带向导的安装程序。
- 不实现自动更新、云同步或账号登录。
- 不把用户数据库放入发布附件。
- 不创建新的 GitHub 仓库。
