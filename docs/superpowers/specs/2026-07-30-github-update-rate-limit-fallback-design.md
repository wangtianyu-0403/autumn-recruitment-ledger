# GitHub 更新限额降级设计

## 目标

解决手动点击“检查更新”时，GitHub 未认证 REST API 因共享公网 IP
配额耗尽而返回 `HTTP 403: rate limit exceeded` 的问题。

程序继续优先使用 GitHub REST API；仅当 API 返回 `403` 或 `429`
限额错误时，自动改用公开 GitHub Release 页面获取同样的版本、附件地址和
SHA-256。用户不需要创建或配置 GitHub Token。

本次修复保持应用版本 `v1.1.0`，不修改数据库、数据目录、ZIP 安装流程或
启动时行为，也不增加自动检查更新。

## 根因

- `fetch_latest_release()` 每次手动检查都会请求
  `api.github.com/repos/wangtianyu-0403/autumn-recruitment-ledger/releases/latest`。
- 请求没有身份验证，因此 GitHub 按来源公网 IP 统计 REST API 配额。
- 未认证配额为每小时 60 次；同一公网 IP 上的其他工具也会共享该额度。
- 配额为零时 GitHub 返回 `403` 或 `429`，现有代码直接将异常显示给用户，
  没有备用元数据来源。

## 更新信息获取流程

### 主路径：GitHub REST API

保留当前 API 请求和 JSON 校验逻辑。API 成功时直接返回 `ReleaseInfo`，
不访问 GitHub 网页。

### 降级路径：GitHub Release 页面

仅在 API 请求返回 `HTTP 403` 或 `HTTP 429` 时执行：

1. 请求
   `https://github.com/wangtianyu-0403/autumn-recruitment-ledger/releases/latest`，
   允许 GitHub 跳转到最新正式 Release。
2. 从最终 URL
   `/wangtianyu-0403/autumn-recruitment-ledger/releases/tag/<tag>`
   中提取并解析版本标签。
3. 请求
   `/wangtianyu-0403/autumn-recruitment-ledger/releases/expanded_assets/<tag>`。
4. 使用标准库 `html.parser.HTMLParser` 读取精确附件
   `autumn-recruitment-ledger-Windows-x64.zip` 的下载链接和
   `sha256:<64位十六进制>` 摘要。
5. 构造与 API 路径完全相同的 `ReleaseInfo`，后续下载、摘要校验、ZIP
   安全校验和安装回滚流程保持不变。

## 安全约束

- 最新 Release 最终 URL 的协议必须是 `https`，主机必须精确为
  `github.com`。
- 最终 URL 的仓库路径必须精确为
  `/wangtianyu-0403/autumn-recruitment-ledger/releases/tag/`。
- 附件下载路径必须属于同一仓库、同一标签，并且文件名必须精确匹配
  `autumn-recruitment-ledger-Windows-x64.zip`。
- SHA-256 必须使用 `sha256:` 前缀，并包含正好 64 个十六进制字符。
- 网页结构缺失、跳转到其他域名、标签无效、附件或摘要不匹配时立即抛出
  `UpdateError`，不得下载或安装。
- 不在源码、配置文件或用户电脑中保存 GitHub Token。

## 错误处理

- API 的非限额错误继续显示现有 GitHub 更新信息读取错误。
- API 限额触发后，如果网页降级成功，用户不会看到错误窗口。
- 如果 API 和网页降级都失败，错误消息明确说明 API 已受限以及备用 Release
  信息读取失败的原因。
- 不进行循环重试，避免在受限期间继续消耗请求或触发 GitHub 滥用保护。

## 测试与交付

- 测试 API 正常时不调用网页降级路径。
- 先用失败测试复现 `HTTP 403`，再验证网页降级能解析标签、附件链接和摘要。
- 测试 `HTTP 429` 使用同一降级路径。
- 测试非限额 HTTP 错误不降级。
- 测试错误域名、错误仓库路径、错误附件名、缺失或非法摘要均被拒绝。
- 保留现有下载哈希不匹配、ZIP 路径穿越和安装回滚测试。
- 使用当前已耗尽配额的真实网络环境验证“检查更新”仍能识别 `v1.1.0`。
- 运行完整测试、重新打包并同步本地稳定安装；不创建新 GitHub Release。
