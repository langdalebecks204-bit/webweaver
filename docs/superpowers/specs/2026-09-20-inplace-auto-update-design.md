# 系统应用内差量热更新设计方案

## 1. 背景与目标

在 iStoreOS、OpenWrt 等软路由以及 PVE LXC（CT）宿主机的 Docker 容器环境中：
- 设备内存通常较小（1G~2G，且常无 swap），闪存存储（eMMC/TF卡）有限且寿命敏感。
- 每次版本更新如果都全量重新拉取 150MB~200MB 的多架构 Docker 镜像，不仅下载耗时长（国内拉取 ghcr.io 经常受阻超时），还对存储造成额外的磨损写入。
- **核心目标**：提供**Web 界面内一键差量热更新**能力。从 GitHub Release 下载仅包含编译好的前端静态文件与后端源码的极小增量包（约 3MB~5MB），免敲终端命令，在网页上一键无缝升级，几秒内自动重启并刷新生效。

---

## 2. 总体架构与执行流程

```text
[GitHub Tag Push]
       │
       ▼
 [GitHub Actions] ──► 编译前端 + 打包 app/ 与 dist/ + 生成 version.json
       │              生成 webweaver-update.tar.gz (3~5MB)
       ▼
[GitHub Releases] ──► 挂载 release asset
       │
       │ (网络请求：直连或 ghproxy 加速镜像)
       ▼
[WebWeaver Docker 容器]
       │
   1. [GET /api/system/update/check]
       │   获取最新版本、更新日志、包体积、下载链接
       ▼
   2. [POST /api/system/update/apply]
       │   ① 环境预检 (生产容器 vs 本地开发防护)
       │   ② 流式下载到临时目录
       │   ③ 校验 tar.gz 结构及关键文件完整性
       │   ④ 备份当前运行代码 (/app/backend/app, /app/frontend/dist)
       │   ⑤ 解压覆盖至运行目录 (若异常自动回滚)
       │   ⑥ 依赖项增量补充 (requirements.txt) & 数据库结构迁移 (init_db)
       │   ⑦ 立即返回 200 OK，后台延时 1 秒触发 os._exit(0)
       ▼
[Docker 守护进程]
       │
       └──► 检测到容器退出，根据 restart: unless-stopped 立即自动重启全新容器
       ▼
[前端网页轮询]
       │
       └──► 定时请求 /api/health，服务恢复后自动刷新页面 (window.location.reload())
```

---

## 3. 详细设计

### 3.1 GitHub Actions Release 自动产物
在 `.github/workflows/publish.yml` 中增强构建流程：
- 当触发版本 Tag（如 `v*` 或 `[0-9]*`）时：
  1. 保留现有的 Docker 镜像构建并推送到 GHCR。
  2. 增加增量包打包步骤：
     - 安装 Node.js 20 依赖并执行 `npm run build`，产出 `frontend/dist`。
     - 生成 `version.json`：
       ```json
       {
         "version": "${{ steps.meta.outputs.version }}",
         "built_at": "${{ steps.timestamp.outputs.time }}"
       }
       ```
     - 归档为 `webweaver-update.tar.gz`：
       - `version.json`
       - `frontend/dist/`
       - `backend/app/`
       - `backend/requirements.txt`
     - 使用 GitHub Release 动作创建或更新当前 Tag 的 Release，并将 `webweaver-update.tar.gz` 挂载为资产附件。

### 3.2 后端接口与核心逻辑

#### 接口定义
所有接口均归入 `/api/system/update` 路径下，需管理员（Admin）权限认证：

1. **`GET /api/system/update/check`**
   - **请求参数**：
     - `mirror`: 镜像加速前缀，默认空（如 `https://ghproxy.net/`）。
   - **响应结构**：
     - `current_version`: 当前版本号（从环境变量、FastAPI metadata 或 version.json 读取）。
     - `latest_version`: 最新 GitHub Release 版本号。
     - `has_update`: 是否有新版本（根据 semver 比较）。
     - `release_notes`: 更新日志（Release Body）。
     - `published_at`: 发布时间。
     - `download_url`: 资产下载链接（若指定 mirror 则拼接对应前缀）。
     - `size`: 增量包字节数。

2. **`POST /api/system/update/apply`**
   - **请求结构**：
     - `download_url`: 目标下载包地址。
     - `mirror`: 可选的镜像前缀。
   - **核心步骤**：
     1. **环境防护**：检查环境变量 `WEAVER_ALLOW_INPLACE_UPDATE` 或检测是否在容器环境中（如目录 `/app/backend/app` 与 `/app/frontend/dist` 是否存在）。若在本地 git 源码仓库且未显式开启标志，拒绝执行，保护开发者代码。
     2. **下载与校验**：流式下载至 `/tmp/webweaver_update.tar.gz`，读取并验证 tar 包含有 `version.json`、`backend/app/main.py`、`frontend/dist/index.html`。
     3. **安全备份**：将当前的 `/app/backend/app` 与 `/app/frontend/dist` 复制到备份目录 `/tmp/weaver_backup/`。
     4. **解压替换**：解压新内容直接覆盖 `/app/backend/app` 和 `/app/frontend/dist`（或 `WEAVER_FRONTEND_DIR`）。若发生任何异常，自动还原备份并抛出错误。
     5. **轻量依赖与数据库迁移**：
        - 若 `backend/requirements.txt` 有新增依赖行，调用 `pip install --no-cache-dir -r ...` 进行补齐。
        - 调用 `init_db()` 执行 SQLite 的最新表结构迁移与补充。
     6. **异步延时重启**：
        - 向调用方返回成功结果：`{"status": "success", "message": "更新成功，系统正在重启..."}`。
        - 启动后台异步任务，延时 1 秒后执行 `os._exit(0)`。
        - 容器主进程退出，由 Docker 的 `restart: unless-stopped` 策略瞬间重启容器。

### 3.3 前端交互界面

#### 界面组件
- 新增组件 `frontend/src/components/UpdatePanel.vue`。
- 在 `frontend/src/views/MainView.vue` 的标签页中，为管理员增加【系统更新】标签页（`name="update"`）。

#### 交互行为
1. **版本信息卡片**：
   - 当前版本标签（如 `v0.5.4`）、系统运行环境标签。
   - 镜像源下拉框：预设“官方直连 (GitHub)”、“ghproxy.net (推荐国内)”、“gh-proxy.com (备用)”及“自定义”。
   - 【检查更新】按钮：支持手动触发检查，具备 loading 状态。
2. **发现新版本卡片**：
   - 显示最新版本标签、更新时间、差量包大小。
   - 展示 Release Notes（更新说明与 Bug 修复列表）。
   - 【一键热更新】按钮。
3. **升级进行态对话框**：
   - 弹出升级确认框，告知预计耗时 3~5 秒。
   - 确认后显示阶段进度条：
     - “正在下载与校验差量更新包...”
     - “解压覆盖与升级系统组件...”
     - “服务正在重启，等待重新就绪...”
   - 进入健康检查轮询阶段：每 1 秒请求 `/api/health`（超时 1.5s，最大重试 30 次）。
   - 一旦健康检查返回 HTTP 200，提示“升级成功”，调用 `window.location.reload()` 刷新进入新版本。

---

## 4. 容错与防御策略

1. **断网与下载破损防御**：下载包使用完整性检验，必须是合法 gzip 且包含必备文件，否则拒绝解压。
2. **热更回滚机制**：在解压覆盖前保留现场备份副本，解压失败立刻将现场备份还原，确保系统不处于半生不熟的损坏状态。
3. **本地开发环境保护**：严格限制执行条件，防止非容器环境执行覆盖本地开发代码。
4. **数据库平滑迁移**：启动与热更均复用已有的幂等迁移逻辑（`init_db` / `_migrate_schema`），确保新增字段自动补齐且数据不丢失。
