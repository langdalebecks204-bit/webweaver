# 系统自动/手动差量更新（免整包拉取 Docker 镜像）设计方案

## 1. 背景与目标
在 iStoreOS / OpenWrt 等软路由与轻量级宿主机设备上：
- 设备内存有限（通常 1G~2G，且无 swap），闪存存储（eMMC/TF卡）有限且寿命敏感。
- 每次更新拉取 150MB~200MB 的多架构 Docker 镜像既慢（国内拉取 ghcr.io 容易受阻超时），又对闪存有较大写入负担。
- 目标：提供**应用内一键自动/手动差量更新**能力，从 GitHub Release 下载仅包含编译好的前端与后端源码的极小包（3MB~5MB），免敲终端命令，在网页内一键升级，并在几秒内平滑重启。

---

## 2. 核心架构设计

### 2.1 GitHub Actions Release 自动产物
在 `.github/workflows/docker.yml`（或 release workflow）中增加一步：
1. 编译前端：`npm --prefix frontend run build`（产出 `frontend/dist`）。
2. 打包：将 `frontend/dist` + `backend/app` + 版本元数据打包成 `webweaver-update.tar.gz`。
3. 发布：自动挂载到 GitHub Release 的 Assets 中供下载。

### 2.2 接口设计
- `GET /api/system/update/check`
  - 向 GitHub Releases API 请求最新版本与 assets 列表。
  - 支持配置或指定国内代理镜像（如 `https://ghproxy.net/`）。
  - 返回：`has_update` (bool), `current_version`, `latest_version`, `release_notes`, `download_url`, `size`。
- `POST /api/system/update/apply`
  - 下载 3MB 的 `webweaver-update.tar.gz` 至临时目录。
  - 解压并覆盖当前运行目录：
    - 前端静态目录：`/app/frontend/dist`
    - 后端源码目录：`/app/app`
  - 自动执行数据库迁移（启动函数 `_migrate_schema()`）。
  - 触发热重载或安全重启（`os.execv` 或配合 docker `--restart` 的退出）。

### 2.3 前端交互界面
- 在“设置”或导航栏右上角增加“系统更新”卡片：
  - 显示当前版本号与“检查更新”按钮。
  - 若有新版，弹出提示卡片，展示新版本号、更新日志、加速镜像选择（直连 / ghproxy加速）与“一键更新”按钮。
  - 点击更新后显示进度条（下载 -> 解压 -> 重启），3~5 秒后自动刷新页面。

### 2.4 关键防御与容错机制
1. **依赖库变更保护**：解压后若检测到 `requirements.txt` 存在新依赖，自动执行轻量 `pip install`，若安装失败则告警建议更新完整镜像。
2. **下载校验**：校验下载包的 SHA256 或 zip 完整性，避免因网络中断导致半包损坏。
3. **备份回滚**：解压覆盖前保留上一个版本的备份副本，若解压异常自动快速恢复。
