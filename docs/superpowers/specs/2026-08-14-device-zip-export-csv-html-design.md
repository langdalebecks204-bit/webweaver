# 设计：设备资产 ZIP 导出升级（CSV + HTML 并存）

日期：2026-08-14
状态：已批准

## 背景与目标

0.4.1 的"导出 ZIP"内含 `设备资产.csv` + `images/`。用户希望 ZIP 内同时提供可视化 HTML 总览（图片缩略图直接显示），CSV 保留供 Excel 分析。UI 收敛为单一"导出 ZIP"按钮，移除独立"导出 CSV"按钮。

## 决策（已与用户确认）

- **并存**：ZIP 内同时含 `设备资产.csv` 与 `设备资产.html`，图片仍在 `images/` 文件夹
- **UI 收敛**：只保留"导出 ZIP"按钮；"导出 CSV"按钮移除（CSV 内容进 ZIP 内部，能力不丢）
- **HTML 图片展示**：缩略图列 `<img src="images/xxx.jpg">`（相对路径，解压后可见），无图设备显示 `-`
- **图片不内嵌**：保持链接引用，避免 base64 膨胀，体积 = 原图之和

## 架构与组件

### 新文件/改动 `frontend/src/utils/exportZip.js`

- 新增 `buildDeviceHtml({ rows, columns })` → `string`
  - 内嵌 `<style>`：简洁表格、状态撞色（在线绿/离线红/警告黄/未知灰）、缩略图固定尺寸
  - 表格列：名称、类型（中文 `typeLabel`）、所属分组、IP、端口、位置、状态（中文）、延时、最近巡检、图片
  - 图片列：有 `image_file` 时 `<img src="images/xxx.jpg">`，否则 `-`
  - `<title>`/`<h1>` 含导出时间
- `buildExportZip` 改为：写入 `设备资产.csv`（现有 `toCsv`）+ `设备资产.html`（新 `buildDeviceHtml`）+ `images/`
- 列配置由调用方传入，`DeviceTable` 复用现有 `zipColumns`（含 `image_file` 列）
- 保留现有 `imageFileName`、`fetchImageBlob`、图片 fetch 失败跳过逻辑

### 改动 `frontend/src/components/DeviceTable.vue`

- 移除"导出 CSV"按钮与 `onExport`
- `csvColumns` 保留供 `zipColumns` 复用；`onExportZip` 传入含 `image_file` 的列
- 保留空数据提示、成功/失败提示逻辑

## 数据流

1. 点击"导出 ZIP" → `onExportZip()`
2. 空数据 → `ElMessage.warning('无数据可导出')`
3. 非空 → `buildExportZip({ rows, csvColumns: zipColumns })`
   - 并行 fetch 图片 → 写入 `images/{name}_{id}.jpg`
   - 写入 `设备资产.csv`（`toCsv`）
   - 写入 `设备资产.html`（`buildDeviceHtml`）
4. `downloadCsv(...zip)` 下载 → `ElMessage.success('已导出 N 条记录')`
5. 异常 → `ElMessage.error('导出失败')`

## 错误处理

- 单张图 fetch 失败 → 跳过该图不入 ZIP，`image_file` 置空，HTML 图片列显示 `-`，不中断
- 打包异常 → `ElMessage.error('导出失败')`
- 无数据 → `ElMessage.warning('无数据可导出')`

## 测试要点

### `frontend/src/utils/__tests__/exportZip.spec.js`（新增用例）

1. ZIP 同时含 `设备资产.csv` 与 `设备资产.html`
2. HTML 含 `<table>`、中文类型标签、状态文本
3. HTML 有图行含 `<img src="images/核心交换机_12.jpg">`，无图行图片列含 `-` 且不含 `<img`
4. HTML 含 `<style>` 与状态样式类
5. fetch 失败时 HTML 图片列仍为 `-`，不抛异常

### `frontend/src/components/__tests__/DeviceTable.spec.js`（改）

6. 工具栏存在"导出 ZIP"按钮，不存在"导出 CSV"按钮
7. 有数据导出提示条数；空数据提示无数据（沿用现逻辑）

## 明确不做的（YAGNI）

- 不做 HTML 内图片 base64 内嵌（保持链接引用防膨胀）
- 不做多个导出格式的下拉菜单（单一按钮）
- 不改后端任何逻辑