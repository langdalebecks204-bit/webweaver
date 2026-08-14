# 设备类型扩展与表格 CSV 导出 设计文档

日期：2026-08-14
状态：已确认

## 背景

- 设备类型目前为后端正则硬编码 `group/server/switch/terminal` 四种，前端下拉同样写死，类型在表格/详情中以英文原文显示。
- 用户需要：① 扩充设备类型（添加摄像头、NVR、路由器、防火墙、AP、打印机、NAS、UPS）；② 支持用户自定义新类型；③ 设备资产表格可导出为 EXCEL（CSV 格式）。

## 目标

1. 内置 12 种设备类型，每种配专属图标，树/下拉/表格/详情显示中文名。
2. 支持自定义设备类型：添加、删除；删除自定义类型时，引用该类型的设备改回 `terminal`。
3. 设备表格（DeviceTable.vue）可将当前筛选结果导出为 CSV，Excel 打开中文不乱码。
4. 不修改设备表结构（`Device.type` 仍为 `String(20)`），向后兼容现有数据与备份。

## 设计

### 1. 设备类型体系

**内置类型集合**（常量，前后端各有定义，保持一致）：

```
group, server, switch, terminal, camera, nvr, router, firewall, ap, printer, nas, ups
```

**后端**：

- models.py 表结构不变。
- 新增常量与工具函数（如 `app/services/device_types.py`）：
  - `BUILTIN_TYPES` 列表
  - `get_custom_types(db)` 从 `settings` 表读取 `custom_device_types` key（JSON 数组），默认 `[]`
  - `is_valid_type(db, t)`：`t in BUILTIN_TYPES or t in get_custom_types(db)`
- `schemas.py`：`type` 字段校验从固定正则 `^(group|server|switch|terminal)$` 改为运行时校验（pydantic `field_validator`，需访问 DB 时改为在路由层校验，或使用宽松 pattern + 路由层校验）。
  - 方案：schema 只保留基础规则（非空、`^[a-zA-Z0-9_-]{1,20}$`），路由层在创建/更新设备时用 `is_valid_type()` 校验，不合法返回 422。
- 类型管理接口（admin 权限，新增 `app/routers/device_types.py` 或并入 settings router）：
  - `GET /api/settings/device-types` → `{ "builtin": [...], "custom": [...] }`
  - `POST /api/settings/device-types` body `{ "name": "..." }`，添加自定义类型。
    校验：非空、`^[a-zA-Z0-9_-]{1,20}$`、不与内置重复、不与现有自定义重复。
  - `DELETE /api/settings/device-types/{name}`，删除自定义类型：
    - 只允许删除自定义类型（内置不可删，返回 422/400）。
    - 事务内：删除 key 中该名称 + `UPDATE devices SET type='terminal' WHERE type=:name`。
- `backup_service.py` 的 `_VALID_TYPES` 同步为「内置 + 当前自定义类型」，导入备份不再误拒自定义类型。
- UI 下拉所需数据的来源统一为 `GET /api/settings/device-types` + 中文映射。

**前端**：

- 类型中文映射常量（`frontend/src/components/deviceTypeIcons.js` 或独立 `deviceTypes.js`）：
  `group→分组、server→服务器、switch→交换机、terminal→终端、camera→摄像头、nvr→NVR、router→路由器、firewall→防火墙、ap→无线AP、printer→打印机、nas→NAS、ups→UPS`
- 设备新建/编辑下拉（DeviceTree.vue：146-151 行附近；MainView.vue：350-354 行附近）= 内置类型 + 自定义类型（从设置接口拉取）。
- DeviceTable.vue 第 78-80 行类型列、DeviceDetail.vue 第 136 行类型显示改为中文。

### 2. 类型图标

每个内置类型配专属 Element Plus 图标（树视图里区分显示；下拉选项也带图标）。映射：

| 类型 | 图标 |
|---|---|
| group | Folder |
| server | Monitor |
| switch | Connection |
| terminal | Laptop |
| camera | VideoCamera |
| nvr | Film |
| router | Position |
| firewall | Lock |
| ap | Cellphone |
| printer | Printer |
| nas | Files |
| ups | Lightning |

自定义类型 → 默认图标 `Monitor`；加载中/未知类型 → `QuestionFilled`。
（具体图标以 Element Plus 实际存在为准，实现时核对。）

- `DeviceTree.vue`：把图标判断逻辑抽出为 `getTypeIcon(type)`（放入 `deviceTypes.js`），后续想加图片图标只改这一处。传给子节点。

### 3. CSV 导出（纯前端）

- DeviceTable.vue 顶部工具栏加「导出 CSV」按钮（登录用户均可用，不限 admin）。
- 导出数据 = 当前已筛选的 `filteredDevices`（搜索框 + 状态下拉筛选后的即时结果）。
- 列顺序与表格一致：名称、类型（中文）、所属分组、IP、端口、位置、状态（中文）、延时、最近巡检（本地化时间）。
- CSV 生成函数（`frontend/src/utils/csv.js`）：
  - 前置 `\uFEFF` BOM，Excel 打开中文不乱码。
  - 字段含逗号/引号/换行 → 双引号包裹，内部引号加倍转义。
  - 空值填空白。
  - 状态/延时/时间转可读中文：`在线/离线/警告/未知`、`12 ms`、`2026-08-14 10:30`。
- 无后端改动、无新 npm 依赖。
- 数据为空（筛选结果 0 条）时提示「无数据可导出」，不生成文件。

### 4. 设置面板 + 集成

- SettingsPanel 增加「设备类型管理」区域：
  - 列表：内置类型（标「内置」，不可删）+ 自定义类型（可删）。
  - 「添加自定义类型」输入框 + 按钮。
  - 删除自定义类型二次确认提示「该类型下的设备将改为『终端』」。
- settings store（新建或并入现有 store）：
  - `fetchDeviceTypes()`、`addDeviceType(name)`、`removeDeviceType(name)`。
  - 增删后刷新类型列表并刷新设备树（删除类型会改设备 type）。

### 5. 测试与验收

**后端（pytest，复用现有 conftest）**：

- 添加自定义类型成功 / 重名 / 与内置重复 / 超长 / 非法字符 → 校验。
- 删除自定义类型 → 引用该类型的设备变 terminal。
- 删除内置类型 → 拒绝。
- 创建设备时传自定义类型成功 / 传未注册类型 → 422。
- 备份导入含自定义类型的备份可成功。

**前端（vitest，现有 spec 模式）**：

- CSV 序列化函数单测：BOM、逗号/引号/换行转义、空值。
- 类型中文映射：12 种内置 + 自定义默认。
- 导出按钮点击触发下载（mock URL.createObjectURL）。

**手动验收**：登录 → 表格筛选 → 导出 CSV → Excel 打开中文正常；设置中增/删自定义类型，确认树、下拉、表格、详情实时生效。

## 明确不做的（YAGNI）

- 不为自定义类型提供图片图标上传（本期所有类型沿用 Element 图标；仅预留 getTypeIcon 函数为未来扩展点）。
- 不做后端批量 CSV 导出接口（数据量小，纯前端足够）。
- 不改数据库结构、不做类型表。
- 不做类型排序/别名字段。

## 风险与备注

- `schemas.py` 现有 pattern 校验移除后，需确保所有写入路径（创建、更新、备份恢复）统一走 `is_valid_type()`，避免类型绕过。
- pydantic schema 无法直接依赖 DB，因此校验放路由层；前端下拉本身只显示合法类型，正常用户不会触发 422。
- Element Plus 图标名如有出入，以图标库实际导出的为准，保证编译通过。