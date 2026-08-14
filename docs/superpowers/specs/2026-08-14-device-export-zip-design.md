# 设计：设备资产 ZIP 导出（含图片）

日期：2026-08-14
状态：已批准

## 背景与目标

设备表格页已有"导出 CSV"功能（前端 jszip 之外，纯文本）。用户希望同时导出设备图片。CSV 是纯文本，无法内嵌图片，因此新增"导出 ZIP"按钮：一个 ZIP 内含当前筛选设备的 CSV 清单 + 图片文件夹，图片按设备对应命名。

## 决策（已与用户确认）

- **打包位置**：前端。新增 jszip 依赖，前端 fetch 图片后本地打包。
  - 复用现有 `toCsv`/`downloadCsv` 与当前筛选结果，无后端改动。
- **图片命名**：`设备名_设备id.jpg`（如 `核心交换机_12.jpg`），存 ZIP 内 `images/` 文件夹。
- **导出范围**：当前筛选出的所有设备；无图片设备的 CSV"图片"列留空，不进 `images/`。
- **UI 入口**：工具栏独立按钮"导出 ZIP"，与"导出 CSV"并列。
- **fetch 失败策略**：单张图 fetch 失败 → 跳过该图不入 ZIP，且 CSV"图片"列留空（对应关系必须准确），不中断整体导出。

## 架构与组件

### 新文件 `frontend/src/utils/exportZip.js`

核心纯函数模块：

- `buildExportZip({ rows, csvColumns, fetchImage })` → `Promise<Blob>`
  - 内部用 jszip 创建 `zip`：
    - 写入 `设备资产.csv`：内容为 `toCsv(rows, csvColumns)`
    - 对每行有 `image_url` 的设备，`fetchImage(row)` 取 blob，成功则写入 `images/{name}_{id}.jpg`
  - 返回 `zip.generateAsync({ type: 'blob' })`
  - `fetchImage` 默认实现：`fetch(row.image_url).then(r => r.blob())`，可注入便于测试

### 改动 `frontend/src/components/DeviceTable.vue`

- `csvColumns` 增加一列 `{ key: 'image_file', header: '图片' }`，值为 `{name}_{id}.jpg`（仅当导出 ZIP 时有图像的设备；CSV 导出时该列固定为空字符串，避免与既有 CSV 行为不一致）。
  - 实现方式：为 ZIP 导出单独构造列数组 `zipColumns = [...csvColumns, { key: 'image_file', header: '图片', format: ... }]`。
- 新增 `onExportZip()`：
  1. `rows = filteredDevices.value`，空则 `ElMessage.warning('无数据可导出')` 返回
  2. 调 `buildExportZip(...)` 生成 blob
  3. `downloadCsv(\`设备资产_${date}.zip\`, blob)` 触发下载（现有 `downloadCsv` 通过 Blob 下载，通用）
  4. `ElMessage.success(\`已导出 ${rows.length} 条记录\`)`
  - 异常 catch → `ElMessage.error('导出失败')`
- 工具栏在"导出 CSV"旁加"导出 ZIP"按钮。

### 新文件 `frontend/src/utils/__tests__/exportZip.spec.js`

用 jszip 回读断言 ZIP 内容：
1. 生成的 ZIP 含 `设备资产.csv` 与 `images/核心交换机_12.jpg`，命名正确
2. 无 `image_url` 的设备不出现在 `images/`，CSV 中该行图片列留空
3. `fetchImage` 失败时不抛异常，该图被跳过
4. 无图设备列表只含 CSV
5. CSV 内容包含类型中文转换等既有 format（复用 `toCsv`）

### 改动 `frontend/src/components/__tests__/DeviceTable.spec.js`

- element-plus mock 保持不变
- 新增测试：
  5. 点击"导出 ZIP"调用导出函数并提示条数（`successMock` 含"已导出"）
  6. 空设备列表点击提示无数据（`warningMock('无数据可导出')`）

## 数据流

1. 用户点"导出 ZIP" → `onExportZip()`
2. `filteredDevices` 逐行；有 `image_url` 的行并行 `fetch` 图片为 blob
3. jszip 写入 CSV + 图片 → `generateAsync({ type: 'blob' })`
4. `<a download="设备资产_日期.zip">` 下载 → `ElMessage.success`

## 错误处理

- 单张图失败 → 跳过（不中断），CSV"图片"列留空
- 打包异常 → `ElMessage.error('导出失败')`
- 无数据 → `ElMessage.warning('无数据可导出')`

## 测试要点

- `exportZip.spec.js`：1–4 覆盖打包与命名/失败/空场景
- `DeviceTable.spec.js`：5–6 覆盖按钮流

## 明确不做的（YAGNI）

- 不做 ZIP 内目录结构选项（仅 `设备资产.csv` + `images/`）
- 不做打包进度 UI（图片量小）
- 不改后端任何逻辑