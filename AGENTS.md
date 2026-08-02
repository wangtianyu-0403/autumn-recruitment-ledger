# 招聘记录台账开发规范

## 项目边界

- 项目名:`Recruitment-Record-Ledger`
- Python 包:`recruitment_ledger`
- 技术栈:Python 3.10+、PySide6、SQLite、pytest、pytest-qt、PyInstaller。
- 程序完全离线,业务数据只保存在本地 SQLite 数据库。
- 禁止加入登录、云同步、在线 API、多人协作或需求外复杂功能。

## 架构约束

- UI、业务逻辑、数据访问分层;UI 中禁止直接编写 SQL。
- SQLite 查询必须参数化,开启外键约束,写操作失败必须回滚。
- 业务模型使用 dataclass 和完整类型注解。
- 用户数据目录必须由 `QStandardPaths.AppDataLocation` 解析,禁止硬编码绝对路径。
- 测试必须注入临时路径,不能访问真实用户数据。
- 数据库升级必须保留已有数据。
- 恢复数据库必须验证、备份当前数据、关闭连接、替换并重新连接。

## 质量与安全

- 用户可见文本和错误提示使用中文。
- 不显示完整 Python 堆栈;开发信息写入滚动日志。
- 禁止 `TODO`、`TBD`、占位 `pass`、假按钮、空菜单和只打印不执行的操作。
- 禁止裸 `except:`;不能静默吞掉异常。
- 不记录完整 JD、联系方式等隐私内容到日志。
- `.venv`、数据库、日志、备份、导出、缓存和构建产物不得提交。
- 所有文本文件使用 UTF-8。

## 验证要求

- 修改数据库或仓储层后运行相关 pytest。
- 最终必须运行完整 `python -m pytest -q`。
- GUI 使用 `QT_QPA_PLATFORM=offscreen` 做可重复冒烟测试。
- Windows 打包前测试必须通过;使用 PyInstaller `--onedir --windowed`。
- README 中只记录已经实际验证的命令。
