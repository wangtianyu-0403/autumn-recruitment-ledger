# “招聘记录台账”产品更名与数据迁移设计

## 目标

将当前“秋招进程台账”正式更名为“招聘记录台账”，发布版本
`v1.1.2`，并将代码、活动文档、构建产物、本地安装目录和 GitHub
地址切换到新品牌。现有用户的本地记录必须安全迁移，不能覆盖或删除旧数据。

目标 GitHub 仓库为：

`https://github.com/wangtianyu-0403/Recruitment-Record-Ledger`

## 命名规则

v1.1.2 使用以下规范名称：

| 对象 | 新名称 |
| --- | --- |
| 产品显示名、窗口标题 | `招聘记录台账` |
| Python 包 | `recruitment_ledger` |
| 本地 Git 项目文件夹 | `C:\Users\wty\Recruitment-Record-Ledger` |
| Windows EXE | `招聘记录台账.exe` |
| PyInstaller 输出根目录 | `招聘记录台账` |
| 本地安装目录 | `%LOCALAPPDATA%\Programs\RecruitmentRecordLedger` |
| Windows 应用标识 | `RecruitmentRecordLedger` |
| Release 资产 | `Recruitment-Record-Ledger-Windows-x64.zip` |
| ZIP 内程序根目录 | `招聘记录台账` |
| 日志文件 | `recruitment_ledger.log` |
| 新建自动备份 | `recruitment_record_YYYYMMDD.db` |

活动源码、测试、README、AGENTS、构建脚本、更新器和当前版本文档中的
“秋招”及旧产品英文标识全部切换到新名称。以下内容属于明确例外：

- 主数据库文件继续命名为 `autumn_recruitment.db`，遵循用户要求。
- 已经存在的旧备份文件不改名；新版备份清理逻辑同时识别旧、新两种备份名。
- 历史 Git 提交、旧标签、旧 Release 及描述旧版本事实的历史设计/计划文档不重写。

## 代码和文件迁移

Python 包目录由 `autumn_ledger` 重命名为 `recruitment_ledger`，并同步修改所有
导入语句、入口文件、测试和构建配置。PyInstaller spec、构建脚本、本地同步脚本、
桌面快捷方式、README 和更新器中的路径均使用新名称。

本地仓库完成并验证后，从
`C:\Users\wty\autumn-recruitment-ledger`
重命名为
`C:\Users\wty\Recruitment-Record-Ledger`。
Git `origin` 同步更新到新仓库地址。重命名必须保留 `.git` 和完整提交历史。

本机开发同步成功后，创建指向新 EXE 的“招聘记录台账”桌面快捷方式。确认新程序
启动正常后，移除旧的“秋招进程台账”快捷方式和旧程序安装目录；用户数据目录不在
该清理范围内。

## 用户数据迁移

旧数据根目录：

`%APPDATA%\PersonalTools\AutumnRecruitmentLedger`

新数据根目录：

`%APPDATA%\PersonalTools\RecruitmentRecordLedger`

迁移发生在数据库初始化之前，规则如下：

1. 新目录中已存在主数据库时，直接使用新数据库，不覆盖它。
2. 新目录没有主数据库且旧数据库存在时，创建新目录并开始迁移。
3. 使用 SQLite backup API 将旧数据库一致地复制到新目录中的临时数据库，避免
   WAL 文件或未检查的普通文件复制造成记录缺失。
4. 对临时数据库运行 `PRAGMA integrity_check`，结果必须为 `ok`。
5. 验证成功后，以原子替换方式将临时数据库放到新目录，文件名仍为
   `autumn_recruitment.db`。
6. 迁移旧目录中仍有价值的备份和导出文件时只复制、不覆盖同名文件；日志不迁移。
7. 旧数据目录始终保留，作为用户可见的迁移备份，不自动删除。

如果旧数据库无法打开、复制或通过完整性检查，新版不得悄悄创建空数据库。程序应
显示明确错误，指出旧数据库路径、失败原因和旧数据仍被保留，然后终止本次启动。

没有旧数据库的新用户直接在新目录创建空数据库。

## 更新兼容性

v1.1.2 更新器改用新 GitHub 仓库、新 Release 资产、新 ZIP 根目录和新 EXE 名称。
更新器的 API 与网页回退路径均使用大小写准确的
`wangtianyu-0403/Recruitment-Record-Ledger`。

v1.1.1 更新器会查找并校验旧资产、旧 ZIP 根目录和旧 EXE 名称，因此不能安全地
直接安装完全更名后的 v1.1.2。本次升级采用一次性手动迁移：

1. 用户从新仓库的 v1.1.2 Release 下载 ZIP。
2. 解压并运行 `招聘记录台账.exe`。
3. 新程序自动迁移旧数据库。
4. 从 v1.1.2 开始，后续版本继续使用程序内“检查更新”。

不发布包含旧品牌目录或旧 EXE 的兼容资产，以满足完整更名要求。README 和 Release
说明必须明确写出这次一次性手动升级步骤。

## 发布物与版本

- 应用版本和右下角版本文字更新为 `v1.1.2`。
- Windows 便携包不包含数据库、备份、导出、日志、源码、测试或开发环境。
- 应用图标继续使用现有 `assets\ui.ico`。
- GitHub `main` 接收验证后的代码。
- 创建 `v1.1.2` 标签和非草稿、非预发布 Release。
- Release 上传 ZIP 和对应 SHA-256 校验值。

## 错误处理

- 数据迁移失败时不删除旧数据库，不留下会被误认为有效的新数据库。
- 新旧数据同时存在时永不自动合并或覆盖，以新数据为准并记录诊断日志。
- 本地程序目录同步失败时保留旧安装目录，只有新 EXE 验证成功后才清理旧程序。
- Release 或更新资产名称不匹配时给出可理解的错误，不尝试安装未知 ZIP。

## 验收与测试

至少覆盖以下测试：

- 全新用户在新数据目录创建数据库，数据库文件名保持不变。
- 只有旧数据库时自动迁移，所有应用记录和状态历史保持一致。
- 包含 WAL 状态的旧数据库可通过 SQLite backup API 完整迁移。
- 新旧数据库同时存在时不覆盖新数据库。
- 损坏的旧数据库迁移失败且原文件仍存在。
- 旧、新自动备份文件均能被保留策略识别。
- 活动源码、测试、README 和构建脚本不再出现旧产品显示名或旧仓库地址；数据库名及
  历史文档例外由精确白名单控制。
- Python 包从新名称导入，完整测试通过。
- 新 EXE 的窗口标题、版本文字、图标和本地数据路径正确。
- 便携 ZIP 在含中文和空格的全新目录解压后可启动，并且 ZIP 内无用户数据库。
- 本地仓库远程地址指向新 GitHub 仓库，推送后的 Release 资产可以下载并校验。

