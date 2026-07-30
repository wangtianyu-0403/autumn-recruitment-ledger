# Windows EXE 应用图标设计

## 目标

将用户提供的 `E:\Users\wty\Desktop\ui.ico` 原样作为秋招进程台账 Windows
EXE 的图标，使资源管理器、任务栏和桌面快捷方式从 EXE 图标资源中读取该
图标。

应用版本继续保持 `v1.1.1`。修改完成后同步本地安装，推送 GitHub `main`，
并替换现有 `v1.1.1` Release 中的 Windows ZIP 与 SHA-256；不移动或重写
现有 `v1.1.1` Git 标签。

## 输入图标

- 源文件是有效 ICO，包含一个 `16×16`、24 位图层。
- 本次按用户选择原样使用，不重绘、不放大、不生成新的图标设计。
- 小图标和快捷方式场景可正常显示；Windows 大图标模式会放大原始 16×16
  图层，可能出现像素化，这是输入资源的固有限制。

## 仓库与构建

- 将源文件复制为仓库内的 `assets/ui.ico`，使构建不依赖桌面绝对路径。
- `scripts/build_windows.bat` 的 PyInstaller 命令增加
  `--icon "assets\ui.ico"`。
- `scripts/sync_local_windows.ps1` 的 PyInstaller 命令增加
  `--icon ".\assets\ui.ico"`。
- 不修改 macOS/Linux 构建脚本。
- 桌面快捷方式继续使用安装 EXE 的第 0 个图标资源：
  `IconLocation = "<安装目录>\秋招进程台账.exe,0"`。

## 验证

- 校验 `assets/ui.ico` 的 ICO 头、图层数量、尺寸和位深与源文件一致。
- 运行完整测试套件。
- 通过实际 PyInstaller 构建生成 EXE。
- 使用 PE 资源检查确认 EXE 包含 `RT_GROUP_ICON` 和 `RT_ICON` 资源。
- 本地同步后确认安装 EXE 与构建 EXE 哈希一致，桌面快捷方式仍指向安装 EXE
  并读取第 0 个图标资源。
- 版本标签继续显示 `版本v1.1.1`。

## GitHub 同步

- 将图标资产、构建配置和说明提交并推送到 `main`。
- 生成新的最小 Windows ZIP，执行隐私审计和 `validate_update_archive()`。
- 在现有 `v1.1.1` Release 中删除旧的同名 ZIP，然后上传新的同名 ZIP。
- 更新 Release 说明中的文件 SHA-256。
- 不删除 Release，不删除或强制移动 Git 标签。
- 核对 Release 仍为非草稿、非预发布，附件名称、大小、摘要均与本地一致，
  直接下载返回 HTTP 200。

## 同版本限制

已经安装 `v1.1.1` 的程序会认为版本号相同，因此不会通过“检查更新”重复安装
这次只有图标变化的包。用户本机通过开发同步脚本更新；其他 v1.1.1 用户需要
手动重新下载 ZIP。后续正常功能更新应使用新的语义版本号。
