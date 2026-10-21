# 织网 (WebWeaver) - 完整项目代码架构与文件功能总览

> 本文档详细列出了 WebWeaver 项目中每一个源码文件的职责、核心技术实现与对应业务功能，方便进行代码审查、功能扩展与维护。

---

## 目录
1. [根目录与自动化部署脚本](#1-根目录与自动化部署脚本)
2. [后端核心架构 (backend/app/)](#2-后端核心架构-backendapp)
3. [后端网络探测与调度引擎 (backend/app/inspector/)](#3-后端网络探测与调度引擎-backendappinspector)
4. [后端服务与业务逻辑层 (backend/app/services/)](#4-后端服务与业务逻辑层-backendappservices)
5. [后端 API 控制器路由 (backend/app/routers/)](#5-后端-api-控制器路由-backendapprouters)
6. [后端自动化测试套件 (backend/tests/)](#6-后端自动化测试套件-backendtests)
7. [前端架构、API与状态层 (frontend/src/)](#7-前端架构api与状态层-frontendsrc)
8. [前端组件与视图 (frontend/src/components-&-views/)](#8-前端组件与视图-frontendsrccomponents--views)
9. [前端自动化测试套件 (frontend/src/**/__tests__/)](#9-前端自动化测试套件-frontendsrctests)

---

## 1. 根目录与自动化部署脚本

| 文件路径 | 语言/格式 | 核心功能与职责说明 |
| :--- | :--- | :--- |
| `install.sh` | Shell | **裸机一键自动化部署脚本**：自动适配 Debian/Ubuntu，安装 Python 虚拟环境与依赖、Node.js 20 与前端编译打包、配置 ICMP Raw Socket 特权权限、生成 `.env` 安全凭证并注册开机自启的 Systemd 服务。 |
| `update.sh` | Shell | **一键热更新与 Crontab 定时更新脚本**：在拉取前自动对已有 SQLite 数据库做时间戳安全快照备份（`data/backups/`），自动 `git fetch` 同步源码、更新 Python 依赖、前端增量构建并平滑重启 Systemd 主服务。 |
| `Dockerfile` | Docker | **生产容器构建定义**：多阶段构建镜像（前端静态资源打包 + Python 3.12 运行时），配置轻量级 Web 容器并赋予网络 raw 权限。 |
| `docker-compose.yml` | YAML | **Docker 容器编排**：定义 WebWeaver 容器的服务挂载卷、网络特权（`cap_add: NET_RAW`）、环境变量注入与端口映射。 |
| `.gitignore` | 配置 | **版本控制忽略清单**：全面保护生产数据文件（`data/`, `*.db*`）、环境配置（`.env`）、依赖（`.venv`, `node_modules`）与构建产物。 |

---

## 2. 后端核心架构 (`backend/app/`)

| 文件路径 | 核心功能与职责说明 |
| :--- | :--- |
| [`backend/app/main.py`](file:///d:/code/WebWeaver/backend/app/main.py) | **FastAPI 主应用入口**：装配全局 CORS 中间件、挂载所有 API 路由子模块、配置 SPA 前端静态文件路由托管、管理应用启动初始化与后台探测调度器的启停生命周期。 |
| [`backend/app/config.py`](file:///d:/code/WebWeaver/backend/app/config.py) | **配置管理中心**：基于 Pydantic `BaseSettings`，从环境变量或 `.env` 读取配置（数据库 URL、JWT 密钥、默认凭据、Ping 并发数、超时及轮询间隔）。 |
| [`backend/app/database.py`](file:///d:/code/WebWeaver/backend/app/database.py) | **数据库连接与零停机迁移引擎**：创建 SQLAlchemy Engine 与 Session，启用 SQLite 外键支持；启动时自动执行表结构动态热迁移（`_migrate_schema`），以及历史终端命名规范的平滑数据修复（`_migrate_terminal_names`）。 |
| [`backend/app/models.py`](file:///d:/code/WebWeaver/backend/app/models.py) | **SQLAlchemy ORM 实体模型**：<br>• `User`: 管理员与只读访客账户<br>• `Device`: 核心资产模型（IP、MAC、设备类型、物理端口数、上联口、端口绑定 JSON、SNMP 凭据、虚拟设备标识 `is_virtual` 等）<br>• `ProbeRecord`: 连通性探测流水历史记录（状态、延迟、时间戳）<br>• `ExternalTarget`: 外网/域名/URL 探测目标<br>• `Setting`: 全局 KV 配置项存储 |
| [`backend/app/schemas.py`](file:///d:/code/WebWeaver/backend/app/schemas.py) | **Pydantic 数据验证与序列化模型**：严格校验前后端交互数据，定义 `DeviceCreate`、`DeviceUpdate`、`DeviceOut`、`PortBinding`、`UserOut`、`TokenResponse` 等 DTO 结构。 |
| [`backend/app/security.py`](file:///d:/code/WebWeaver/backend/app/security.py) | **密码安全与凭证管理**：集成 `passlib` (bcrypt) 实现密码安全哈希与验证，集成 `python-jose` 签发与解码带有过期时间的 JWT Access Token。 |
| [`backend/app/deps.py`](file:///d:/code/WebWeaver/backend/app/deps.py) | **FastAPI 权限依赖注入**：提供 `get_current_user` 校验登录态，提供 `require_admin` 严格拦截普通只读用户的增删改敏感操作。 |

---

## 3. 后端网络探测与调度引擎 (`backend/app/inspector/`)

| 文件路径 | 核心功能与职责说明 |
| :--- | :--- |
| [`backend/app/inspector/engine.py`](file:///d:/code/WebWeaver/backend/app/inspector/engine.py) | **异步高并发网络探测核心**：<br>• 基于非阻塞 Socket 实现并发 ICMP Ping（原生支持普通用户与 Raw Socket）；<br>• 异步 TCP 端口握手探测；<br>• 精确测量往返延迟（RTT）；<br>• 实现状态翻转（Status Transition）检测，判定上线/掉线。 |
| [`backend/app/inspector/scheduler.py`](file:///d:/code/WebWeaver/backend/app/inspector/scheduler.py) | **后台探测调度器**：基于 `asyncio` 定时任务，按照用户配置的轮询周期（默认 5 分钟）并发扫描全网设备与外部目标，批量写入探测历史（`ProbeRecord`），自动清理 30 天以前的过期监控日志。 |

---

## 4. 后端服务与业务逻辑层 (`backend/app/services/`)

| 文件路径 | 核心功能与职责说明 |
| :--- | :--- |
| [`backend/app/services/device_service.py`](file:///d:/code/WebWeaver/backend/app/services/device_service.py) | **设备资产核心服务**：负责设备与分组树的创建、重命名、父子节点挂载迁移、级联删除校验、端口绑定配置管理与树形层级重构序列化。 |
| [`backend/app/services/device_types.py`](file:///d:/code/WebWeaver/backend/app/services/device_types.py) | **设备类型服务**：维护系统内置标准设备类型列表（`BUILTIN_TYPES`，包含交换机、非管理交换机、服务器、AP等），并支持持久化管理员自定义的设备类型。 |
| [`backend/app/services/snmp.py`](file:///d:/code/WebWeaver/backend/app/services/snmp.py) | **SNMP 协议底层交互库**：封装原生网络 Socket 实现纯 Python 的 SNMP v1/v2c 查询（`snmp_get`, `snmp_walk`），支持解析 RFC 1213 / IF-MIB / IP-MIB / LLDP-MIB 等标准 OID 树。 |
| [`backend/app/services/lldp.py`](file:///d:/code/WebWeaver/backend/app/services/lldp.py) | **LLDP 骨干链路发现**：通过 SNMP 遍历可管理交换机的 LLDP 与 CDP 邻居表，结合端口序号与对端 Chassis ID / Port ID，智能推导交换机之间的物理连线关系与双向拓扑链路。 |
| [`backend/app/services/fdb_edge.py`](file:///d:/code/WebWeaver/backend/app/services/fdb_edge.py) | **边缘接入与虚拟分线器智能推导**：<br>• 过滤交换机间 Trunk/上联端口；<br>• 单 MAC 端口精准识别为直连终端并自动补齐资料；<br>• 多有线 MAC 端口自动聚合推断为虚拟“非管理傻瓜交换机”；<br>• 无线 AP 漫游噪点收敛（基于 IEEE 802 本地随机 MAC 位与移动 OUI 识别）；<br>• 结合全网 ARP 表实现终端 IP-MAC 自动关联与规范命名（`终端 (未知厂商C8:A3:...)`）；<br>• 提供一键固化入库（`apply_edge_topology`）。 |
| [`backend/app/services/arp.py`](file:///d:/code/WebWeaver/backend/app/services/arp.py) | **全网 IP-MAC 资产台账服务**：从核心交换机/网关通过 SNMP 拉取 ARP 缓存，并结合监控服务器 Linux 本机 `/proc/net/arp` 与 Windows `arp -a` 输出，聚合生成未纳管的活跃终端清单。 |
| [`backend/app/services/oui.py`](file:///d:/code/WebWeaver/backend/app/services/oui.py) | **MAC 厂商离线解析与规整**：内置上千家主流网络与硬件厂商的 OUI 映射字典（Apple, Huawei, Cisco, Intel, TP-Link, H3C 等），支持多种格式 MAC 统一规整与厂商快速解析。 |
| [`backend/app/services/external_service.py`](file:///d:/code/WebWeaver/backend/app/services/external_service.py) | **外部监控目标服务**：封装外网域名/IP/端口/URL 监控目标的增删改查及字典序列化转换。 |
| [`backend/app/services/backup_service.py`](file:///d:/code/WebWeaver/backend/app/services/backup_service.py) | **全量数据备份与灾备恢复**：将系统全部设备资产、分组结构、配置参数、探测历史流式压缩打包为 ZIP 文件导出；提供格式校验、版本兼容升级与一键全量恢复导入。 |
| [`backend/app/services/image_service.py`](file:///d:/code/WebWeaver/backend/app/services/image_service.py) | **设备图片与拓扑封面管理**：处理用户上传的设备真实外观图与机房照片，管理图片存储与清除。 |
| [`backend/app/services/image_worker.py`](file:///d:/code/WebWeaver/backend/app/services/image_worker.py) | **异步截图/缩略图工作线程**：后台线程池队列处理图片缩放与生成。 |
| [`backend/app/services/setting_service.py`](file:///d:/code/WebWeaver/backend/app/services/setting_service.py) | **系统配置读写服务**：封装从 `settings` 数据表中存取系统配置的业务接口。 |
| [`backend/app/services/version_service.py`](file:///d:/code/WebWeaver/backend/app/services/version_service.py) | **版本检测服务**：读取本地版本号，支持从远程 GitHub Releases 接口比对并获取最新发布日志。 |
| [`backend/app/services/update_service.py`](file:///d:/code/WebWeaver/backend/app/services/update_service.py) | **在线热更新调用**：与宿主机更新进程交互，触发后端平滑升级。 |

---

## 5. 后端 API 控制器路由 (`backend/app/routers/`)

| 文件路径 | 对应 URL 前缀 | 接口核心职责与功能 |
| :--- | :--- | :--- |
| [`backend/app/routers/auth.py`](file:///d:/code/WebWeaver/backend/app/routers/auth.py) | `/api/auth` | **认证接口**：登录认证、Token 生成、读取当前登录用户身份。 |
| [`backend/app/routers/devices.py`](file:///d:/code/WebWeaver/backend/app/routers/devices.py) | `/api/devices` | **设备接口**：设备树查询、单设备增删改查、端口绑定、SNMP 详情、单设备历史探测数据拉取。 |
| [`backend/app/routers/topology.py`](file:///d:/code/WebWeaver/backend/app/routers/topology.py) | `/api/topology` | **拓扑推导接口**：交换机骨干链路互联探测（`/lldp-neighbors`）、骨干应用（`/apply-lldp`）、边缘终端推导（`/edge-discover`）、边缘终端一键应用（`/apply-edge`）。 |
| [`backend/app/routers/assets.py`](file:///d:/code/WebWeaver/backend/app/routers/assets.py) | `/api/assets` | **资产台账接口**：全网 IP-MAC 资产台账展示、即时触发整网 ARP 刷新、一键纳管未登记终端。 |
| [`backend/app/routers/device_types.py`](file:///d:/code/WebWeaver/backend/app/routers/device_types.py) | `/api/device-types` | **类型字典接口**：获取系统全部类型列表（内置 + 自定义）、管理自定义设备类型。 |
| [`backend/app/routers/external.py`](file:///d:/code/WebWeaver/backend/app/routers/external.py) | `/api/external-targets` | **外部目标接口**：外网网站、公共 DNS、API 接口等外部监控目标的管理与状态返回。 |
| [`backend/app/routers/backup.py`](file:///d:/code/WebWeaver/backend/app/routers/backup.py) | `/api/backup` | **数据灾备接口**：一键导出系统全量备份 ZIP、上传备份文件并恢复系统。 |
| [`backend/app/routers/settings.py`](file:///d:/code/WebWeaver/backend/app/routers/settings.py) | `/api/settings` | **系统设置接口**：查询和修改系统运行参数（轮询频率、离线判定次数等）。 |
| [`backend/app/routers/system.py`](file:///d:/code/WebWeaver/backend/app/routers/system.py) | `/api/system` | **系统状态接口**：监控服务健康度、检查网络 ICMP 权限、版本信息与触发在线更新。 |
| [`backend/app/routers/users.py`](file:///d:/code/WebWeaver/backend/app/routers/users.py) | `/api/users` | **用户管理接口**：系统用户的增删改查、修改登录密码与角色切换（Admin / Viewer）。 |

---

## 6. 后端自动化测试套件 (`backend/tests/`)

全套包含 **31 个测试模块，210 项** 自动化单测与接口测试用例：

- `conftest.py`: pytest 全局夹具（内存 SQLite、FastAPI 测试客户端 `TestClient`、管理员/普通用户鉴权 Header 构造）。
- `test_fdb_edge_service.py` & `test_fdb_models.py`: 边缘接入与终端推导单测（测试单 MAC 直连、分线器聚合、无线 AP 识别、未登记终端 IP-MAC 匹配入库与终端名称格式化）。
- `test_topology_edge_api.py` & `test_topology_api.py`: 拓扑推导与边缘终端一键应用 API 端到端集成测试。
- `test_lldp_service.py`: LLDP/CDP 骨干发现与端口连线算法测试。
- `test_snmp_service.py`: SNMP 协议底层通信与 OID 树解析测试。
- `test_arp_service.py` & `test_assets_api.py`: ARP 解析与资产台账接口测试。
- `test_devices_api.py` & `test_device_service.py`: 设备增删改查、层级校验与端口配置测试。
- `test_device_image_api.py`: 设备外观与机房照片上传与缩略图测试。
- `test_device_snmp_api.py`: 设备 SNMP 实时端口与流量拉取测试。
- `test_device_types.py` & `test_device_types_api.py`: 设备类型字典与其顺序测试。
- `test_external_api.py` & `test_external_service.py`: 外网目标监控与增删改查测试。
- `test_history_api.py`: 设备 Ping 延迟历史与可用率统计测试。
- `test_models.py`: SQLAlchemy 数据模型约束与外键级联测试。
- `test_oui_service.py`: MAC 地址厂商前缀离线匹配与解析测试。
- `test_database.py`: 数据库零停机列迁移与终端历史名称平滑修复测试。
- `test_engine.py` & `test_scheduler.py`: 异步 ICMP/TCP 探测引擎与定时调度器测试。
- `test_auth_api.py` & `test_security.py`: JWT 鉴权与密码哈希加解密测试。
- `test_backup_api.py`: 备份打包导出与数据恢复全生命周期测试。
- `test_settings_api.py`: 系统全局设置读写与默认参数测试。
- `test_static.py`: 前端 SPA 静态资源路由挂载与 fallback 测试。
- `test_system_api.py`, `test_update_service.py`, `test_version_service.py`: 系统与版本服务测试。

---

## 7. 前端架构、API与状态层 (`frontend/src/`)

### 7.1 应用入口与工具函数
| 文件路径 | 核心功能与职责说明 |
| :--- | :--- |
| `frontend/src/main.js` | **前端应用入口**：创建 Vue 3 实例，挂载 Pinia 状态树、Vue Router，注册 Element Plus 组件与全部 Element Icons。 |
| `frontend/src/App.vue` | **根视图组件**：应用主容器，处理全局主题样式与路由挂载出口（`<router-view>`）。 |
| `frontend/src/router/index.js` | **前端路由中心**：定义登录页 (`/login`) 与监控工作台主页 (`/`)，配置路由前置导航守卫，自动拦截未登录状态。 |
| [`frontend/src/utils/deviceTypes.js`](file:///d:/code/WebWeaver/frontend/src/utils/deviceTypes.js) | **设备类型元数据**：定义各设备类型的中文标签（`DEVICE_TYPE_LABELS`）、Element-Plus 图标（`DEVICE_TYPE_ICONS`）、拓扑图 Emoji 图元（`DEVICE_TYPE_GLYPHS`，非管理交换机与交换机统一定义为 `🔀`）。 |
| [`frontend/src/utils/topologyLinks.js`](file:///d:/code/WebWeaver/frontend/src/utils/topologyLinks.js) | **拓扑链路与速率着色**：定义网络连接速率颜色标准字典（万兆蓝、2.5G荧光绿、千兆绿、百兆橙、离线灰），并计算物理链路的绘制色彩。 |
| `frontend/src/utils/treeToGraph.js` | **拓扑结构转换器**：将后端返回的嵌套设备树与物理端口绑定关系扁平化为 Vis-Network / Canvas 渲染所需的图谱节点与连线数据。 |
| `frontend/src/utils/csv.js` & `exportZip.js` | **导出工具**：支持将资产列表导出为标准 CSV 表格，或流式打包多文件。 |

### 7.2 API 请求封装层 (`frontend/src/api/`)
- `client.js`: 基于 Axios 的全局单例 HTTP 客户端，统一配置 BaseURL、自动携带 Authorization Bearer JWT、捕获 401 自动跳转登录。
- `auth.js`, `devices.js`, `topology.js`, `assets.js`, `settings.js`, `system.js`, `users.js`, `backup.js`, `external.js`: 分别严格对接后端对应的 RESTful API。

### 7.3 Pinia 响应式状态库 (`frontend/src/stores/`)
- `devices.js` & `devicesHelpers.js`: 维护全局设备树节点、拓扑图节点平铺、设备增删改联动响应。
- `assets.js`: 缓存全网 IP-MAC 资产台账列表与刷新状态。
- `auth.js`: 管理当前登录用户 Token、用户名、角色以及登出清理。
- `system.js`: 轮询系统网络特权状态与新版本发布提醒。
- `settings.js`, `users.js`, `external.js`: 分别管理系统参数、用户列表与外部监控目标。

---

## 8. 前端组件与视图 (`frontend/src/components/` & `views/`)

| 组件/视图文件 | 界面与业务交互职责 |
| :--- | :--- |
| `frontend/src/views/MainView.vue` | **监控平台总览主控台**：顶部导航栏（全局指标概览、全屏切换、快速操作按钮）、左侧设备树、中间拓扑图/设备表格、右侧详情抽屉的整体布局与联动控制。 |
| `frontend/src/views/LoginView.vue` | **登录页面**：深色科技风设计，提供账密输入、表单校验、登录提交与错误反馈。 |
| [`frontend/src/components/TopologyView.vue`](file:///d:/code/WebWeaver/frontend/src/components/TopologyView.vue) | **交互式网络拓扑可视化大屏**：<br>• 基于 HTML5 Canvas / Vis-Network 渲染高性能拓扑图；<br>• 支持滚轮缩放、拖拽平移、高亮相邻链路；<br>• 节点显示设备类型 Emoji 图元与在线状态呼吸光环；<br>• 物理连接线根据端口实时速率（百兆/千兆/2.5G/万兆）动态变色；<br>• 顶部集成【⚡ LLDP / 物理拓扑探测】向导入口与速率图例。 |
| [`frontend/src/components/DeviceTree.vue`](file:///d:/code/WebWeaver/frontend/src/components/DeviceTree.vue) | **左侧设备树形控制台**：<br>• 递归渲染分组与子设备层级树，显示节点在线状态指示灯；<br>• 支持右键快捷菜单或行内按钮：新增子节点、编辑节点、端口绑定、查看详情、删除；<br>• 节点编辑对话框内置名称、类型（非管理交换机排在交换机后）、IP、**MAC 地址（选填）**、位置与 SNMP 参数配置。 |
| `frontend/src/components/DeviceTable.vue` | **设备平铺列表视图**：提供设备资产的全局关键字搜索（匹配名称、IP、MAC、位置）、多条件状态筛选、分页与批量导出。 |
| `frontend/src/components/DeviceDetail.vue` | **设备详情抽屉面板**：展示设备基础信息、IP、MAC、位置、SNMP 配置、上联端口状态以及历史可用率统计卡片。 |
| `frontend/src/components/DeviceHistory.vue` | **连通性历史趋势图**：基于 ECharts 折线图直观呈现设备最近 7 天 / 30 天的 Ping 延迟变化与掉线时段。 |
| [`frontend/src/components/SwitchPanel.vue`](file:///d:/code/WebWeaver/frontend/src/components/SwitchPanel.vue) | **交换机物理 RJ45 端口矩阵面板**：<br>• 还原机房交换机真实物理面板；<br>• 顶部集成速率颜色图例（百兆/千兆/2.5G/万兆）；<br>• 端口 LED 指示灯根据当前协商的连接速率动态改变发光色彩与光晕；<br>• 在线端口卡片顶部高亮显示对应的速率色光带；<br>• 鼠标悬停展示端口序号、出入向实时流量与带颜色标识的协商速率。 |
| `frontend/src/components/SwitchPortsModal.vue` | **交换机端口与实时出入向带宽监控**：弹出式大屏，集成 `SwitchPanel` 物理端口矩阵与选中端口的 ECharts 毫秒级入向/出向带宽实时折线图，支持 5s 自动刷新。 |
| `frontend/src/components/PortBindingDialog.vue` | **物理端口连线配置弹窗**：在交换机上直观配置各个端口连向的目标子设备、线缆类型与速率。 |
| [`frontend/src/components/LldpDiscoveryModal.vue`](file:///d:/code/WebWeaver/frontend/src/components/LldpDiscoveryModal.vue) | **物理拓扑探测向导（双页签）**：<br>• **页签 1【交换机骨干互联 (LLDP)】**：展示交换机间物理链路，支持勾选一键固化与自动挂载层级；<br>• **页签 2【边缘终端与分线器推导 (CAM/FDB)】**：精准列出单 MAC 直连终端并支持一键入库，多有线 MAC 聚合为虚拟分线器卡片（支持重命名），无线 AP 漫游噪点智能收敛，完整匹配展示 IP 与 MAC。 |
| `frontend/src/components/AssetsPanel.vue` | **IP-MAC 资产台账控制台**：显示全网在线设备 ARP 映射表，标记已纳管/未纳管状态，支持一键将未纳管终端录入设备树。 |
| `frontend/src/components/BackupPanel.vue` | **系统备份与恢复弹窗**：一键生成全量系统备份 ZIP 下载，支持拖拽备份文件上传恢复。 |
| `frontend/src/components/UpdatePanel.vue` | **系统版本升级控制台**：比对当前版本与 GitHub 最新版本，显示升级说明与一键更新指导。 |
| `frontend/src/components/UsersPanel.vue` | **系统账号管理控制台**：管理员用于创建、编辑用户、重置登录密码与分配只读/管理员权限。 |

---

## 9. 前端自动化测试套件 (`frontend/src/**/__tests__/`)

全套包含 **25 个测试文件，159 项测试** 全部通过：
- `SwitchPanel.spec.js`: 测试 RJ45 端口矩阵、速率变色类名（百兆/千兆/2.5G/万兆）及顶部图例。
- `DeviceTree.spec.js`: 测试设备树递归渲染、节点编辑、MAC 地址字段双向绑定与提交。
- `deviceTypes.spec.js`: 测试设备类型标签、非管理交换机在交换机后的顺序、拓扑图图元符号一致性。
- `LldpDiscoveryModal.spec.js`: 测试双页签物理拓扑向导与边缘接入数据交互。
- `TopologyView.spec.js`: 测试拓扑画布初始化、全屏模式与速率连线算法。
- `topologyLinks.spec.js`: 测试各种速率等级下的颜色匹配函数。
- `PortBindingDialog.spec.js`, `DeviceDetail.spec.js`, `DeviceHistory.spec.js`, `DeviceTable.spec.js`, `AssetsPanel.spec.js`, `BackupPanel.spec.js`, `UpdatePanel.spec.js`, `UsersPanel.spec.js`, `MainView.spec.js`: 前端核心组件的全量交互与渲染测试。
