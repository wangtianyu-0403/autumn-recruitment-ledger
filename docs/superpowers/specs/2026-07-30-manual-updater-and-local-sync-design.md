# 手动在线更新与本地一键同步设计

## 目标

为“秋招进程台账”增加两条更新路径：

1. 开发电脑可以在代码修改后执行一次命令，自动测试、重新打包并同步到稳定的本地安装目录。
2. 已分发给其他用户的程序提供“检查更新”按钮；仅在用户主动点击并确认后，从 GitHub Release 下载、验证并安装新版本。

程序不在启动时自动联网，也不静默安装更新。

## 版本与发布约定

- 当前版本继续由 `autumn_ledger.constants.APP_VERSION` 提供。
- GitHub 正式版本使用语义化标签 `v主版本.次版本.修订版本`，例如 `v1.0.1`。
- 更新源固定为公开仓库 `wangtianyu-0403/autumn-recruitment-ledger` 的 latest release API。
- Windows 更新附件固定命名为 `autumn-recruitment-ledger-Windows-x64.zip`。
- 只接受非草稿、非预发布的正式 Release。
- 版本比较按三个非负整数进行，不使用字符串字典序。

## 应用内检查更新

- 在主窗口工具栏增加“检查更新”按钮。
- 点击后才访问 GitHub，不执行启动自动检查或定时检查。
- 请求设置有限超时，并发送明确的应用标识 User-Agent。
- 网络不可用、API 限流、响应格式错误时，显示简短中文错误，不影响台账其他功能。
- 当前版本不低于远程版本时，提示“当前已是最新版本”。
- 发现新版本时显示当前版本、最新版本和确认按钮；用户拒绝后不下载。

## 下载与安全校验

- 从 Release 数据中精确选择 `autumn-recruitment-ledger-Windows-x64.zip`。
- 将 ZIP 下载到当前用户临时目录中的独立更新目录。
- 计算完整文件的 SHA-256。
- 优先使用 GitHub Release asset 的 `digest` 字段进行校验；字段不存在或不是 `sha256:` 格式时拒绝自动安装，并提示用户前往 Release 页面手动下载。
- 校验失败时删除或隔离临时文件，绝不替换当前程序。
- 安装前检查 ZIP 必须包含：
  - `秋招进程台账/秋招进程台账.exe`
  - `秋招进程台账/_internal/python313.dll`
- 拒绝绝对路径、父目录穿越和逃逸目标目录的 ZIP 条目。

## 外部更新助手

- 正在运行的 EXE 不能安全覆盖自身，因此程序生成临时 PowerShell 更新脚本。
- 程序使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File` 启动脚本，并传入：
  - 当前程序进程 ID
  - 已验证 ZIP 路径
  - 当前程序目录
  - 当前 EXE 路径
  - 更新日志路径
- 脚本等待当前进程退出，再把 ZIP 解压到临时目录。
- 脚本将当前程序目录移动为同级备份目录，再将新版本目录移动到原路径。
- 新程序成功启动后保留一次备份，供人工恢复；后续成功更新可替换上一次备份。
- 替换失败时将备份目录恢复到原路径，并把错误写入中文日志。
- 更新器仅操作程序安装目录，不读取、复制、移动或删除 `%APPDATA%\PersonalTools\AutumnRecruitmentLedger\`。

## 源码运行模式

- 通过 `python main.py` 启动时不执行自动替换。
- 源码模式点击“检查更新”可以查询和显示版本，但确认安装时提示开发者使用本地一键同步脚本。
- 只有 PyInstaller 冻结版本允许启动外部更新助手。

## 本地一键同步

- 新增 `scripts/sync_local_windows.ps1`，并提供双击入口 `scripts/sync_local_windows.bat`。
- 默认安装目录为：

  `%LOCALAPPDATA%\Programs\AutumnRecruitmentLedger\`

- 执行顺序：
  1. 检查虚拟环境并安装开发依赖。
  2. 设置 Qt 离屏平台并运行完整测试。
  3. 测试通过后运行 PyInstaller `--onedir --windowed`。
  4. 将新产物复制到临时安装目录。
  5. 校验 EXE 与 `_internal/python313.dll`。
  6. 若程序正在运行，提示用户关闭并停止同步，不强制终止。
  7. 将现有安装目录移动为备份，再把临时目录移动到稳定安装路径。
  8. 创建或修复当前用户桌面快捷方式，使其指向稳定安装目录。
  9. 启动新程序并显示安装路径。
- 任一步骤失败时保留原安装目录，返回非零退出码并显示中文错误。

## 模块边界

- `autumn_ledger/update.py`
  - 解析与比较版本。
  - 请求和校验 GitHub Release 元数据。
  - 下载并校验 ZIP。
  - 生成和启动外部更新助手。
- `autumn_ledger/ui/main_window.py`
  - 提供“检查更新”按钮。
  - 负责用户确认、进度和中文错误提示。
  - 不直接实现 HTTP、哈希、ZIP 或文件替换。
- `scripts/sync_local_windows.ps1`
  - 只负责开发电脑测试、打包和本地安装。
- `scripts/sync_local_windows.bat`
  - 只负责提供可双击的 PowerShell 启动入口。

## 测试

- 版本解析：合法标签、缺少 `v`、非法段数、非数字和版本大小比较。
- Release 元数据：正式版本、草稿、预发布、缺少目标附件、缺少 digest。
- 下载校验：正确 SHA-256、错误 SHA-256、中断下载。
- ZIP 安全：必需文件存在、缺失运行时、绝对路径、`..` 穿越。
- 源码模式：允许检查但拒绝自替换。
- UI：按钮存在；无更新、有更新、网络错误的消息路径。
- PowerShell 同步脚本：使用临时路径验证失败不覆盖、成功替换和快捷方式目标。
- 最终运行完整 pytest，并重新构建 ZIP 做解压启动验证。

## 发布流程

- 更新功能随下一个版本发布，不覆盖已经公开的 `v1.0.0`。
- 实现完成后将版本提升到 `v1.1.0`。
- 重新构建 `autumn-recruitment-ledger-Windows-x64.zip`。
- 推送 `main` 后创建正式 GitHub Release `v1.1.0`。
- Release 附件必须带 GitHub 可读取的 `sha256:` digest，并完成远程下载验证。

## 非目标

- 不做后台自动检查、启动检查或定时检查。
- 不静默安装更新。
- 不支持跨平台自动更新；首版仅支持 Windows 10/11 64 位。
- 不制作 MSI、Windows 服务或常驻后台进程。
- 不实现账号、云同步或远程数据库迁移。
