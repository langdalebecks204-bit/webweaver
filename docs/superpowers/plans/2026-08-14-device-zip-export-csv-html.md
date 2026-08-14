# 设备资产 ZIP 导出升级（CSV + HTML 并存）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "导出 ZIP"产物升级为同时含 `设备资产.csv` 与 `设备资产.html`（HTML 内缩略图链接引用 images/），UI 收敛为单一按钮。

**Architecture:** 纯前端。`exportZip.js` 新增 `buildDeviceHtml({ rows, columns })` 生成自包含 HTML 字符串；`buildExportZip` 同时写入 CSV + HTML + images/；`DeviceTable.vue` 移除"导出 CSV"按钮。

**Tech Stack:** Vue 3、jszip、vitest、@vue/test-utils。

## Global Constraints

- ZIP 内文件：`设备资产.csv`、`设备资产.html`、`images/{name}_{id}.jpg`
- HTML 图片用相对链接 `<img src="images/{image_file}">`，**不内嵌 base64**
- 无图设备 HTML 图片列显示 `-`，不含 `<img>`
- 状态色：在线绿色/离线红色/警告黄色/未知灰色
- 单图 fetch 失败跳过，HTML 列显示 `-`，不中断
- 无数据 `ElMessage.warning('无数据可导出')`；成功 `ElMessage.success('已导出 N 条记录')`；异常 `ElMessage.error('导出失败')`
- 移除"导出 CSV"按钮，仅保留"导出 ZIP"

---

### Task 1: exportZip.js 新增 HTML 生成与打包扩展

**Files:**
- Modify: `frontend/src/utils/exportZip.js`
- Test: `frontend/src/utils/__tests__/exportZip.spec.js`

**Interfaces:**
- Consumes: 现有 `imageFileName(row)`、`fetchImageBlob(row)`、`toCsv(rows, columns)`（`frontend/src/utils/csv.js`）
- Produces:
  - `buildDeviceHtml({ rows, columns })` → `string`（含 `<style>`/`<table>`/缩略图 `<img src="images/{image_file}">`）
  - `buildExportZip({ rows, csvColumns, fetchImage, htmlColumns })` → `Promise<Blob>`，ZIP 内含 `设备资产.csv` + `设备资产.html`。`htmlColumns` 缺省时取 `csvColumns`
  - `statusClass(status)` → `'st-online'|'st-offline'|'st-warning'|'st-unknown'`（供内部使用）

- [ ] **Step 1: 追加失败测试（exportZip.spec.js 文件内追加用例）**

在 `frontend/src/utils/__tests__/exportZip.spec.js` 的 `describe('buildExportZip')` 内追加（并保持现有用例）：

```js
const htmlCsvColumns = [
  { key: 'name', header: '名称' },
  { key: 'ip_address', header: 'IP' },
  { key: 'status', header: '状态' },
  { key: 'image_file', header: '图片' },
]

describe('buildDeviceHtml', () => {
  const htmlRows = [
    {
      id: 12, name: '核心交换机', type: 'switch', ip_address: '10.0.0.1',
      status: 'online', latency_ms: 5, last_check: '2026-08-14T02:30:00+00:00',
      image_file: '核心交换机_12.jpg',
    },
    {
      id: 13, name: '终端B', type: 'terminal', ip_address: '10.0.0.2',
      status: 'offline', latency_ms: null, last_check: null, image_file: '',
    },
  ]

  it('生成含表格、缩略图与中文标签的 HTML', () => {
    const html = buildDeviceHtml({ rows: htmlRows, columns: htmlCsvColumns })
    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<table>')
    expect(html).toContain('核心交换机')
    expect(html).toContain('switch') // 类型列使用 upstream 值
    expect(html).toContain('在线')   // 状态文本
    expect(html).toContain('<img src="images/核心交换机_12.jpg"')
    expect(html).toContain('st-online')
    expect(html).not.toContain('<img src="images/终端B_13.jpg"')
  })

  it('无图设备图片列显示 - 且不含 img', () => {
    const html = buildDeviceHtml({ rows: htmlRows.slice(1), columns: htmlCsvColumns })
    expect(html).not.toContain('<img')
    expect(html).toContain('终端B')
  })

  it('含标题与导出时间', () => {
    const html = buildDeviceHtml({ rows: [], columns: htmlCsvColumns })
    expect(html).toContain('<h1>') 
  })
})

describe('buildExportZip csv+html', () => {
  it('ZIP 同时含 csv 与 html 文件', async () => {
    const fetchImage = vi.fn(async () => new Blob(['jpg']))
    const blob = await buildExportZip({
      rows,
      csvColumns: [...columns, { key: 'image_file', header: '图片' }],
      fetchImage,
    })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).toContain('设备资产.csv')
    expect(Object.keys(zip.files)).toContain('设备资产.html')
    const html = await zip.file('设备资产.html').async('string')
    expect(html).toContain('<table>')
  })
})
```

（`rows`、`columns`、`readZip` 复用文件顶部现有定义。注意现有 `buildExportZip` 测试中的 `columns` 已不含 `image_file` 列，HTML 缺省复用 `csvColumns`，现有用例仍应通过。）

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- --run src/utils/__tests__/exportZip.spec.js`（在 `frontend/`）
Expected: FAIL — `buildDeviceHtml` 未定义

- [ ] **Step 3: 实现 exportZip.js**

修改 `frontend/src/utils/exportZip.js`，完整内容：

```js
import JSZip from 'jszip'
import { toCsv } from './csv'

const ILLEGAL = /[\\/:*?"<>|]/g

export function imageFileName(row) {
  return `${String(row.name).replace(ILLEGAL, '_')}_${row.id}.jpg`
}

export function statusClass(status) {
  if (status === 'online') return 'st-online'
  if (status === 'offline') return 'st-offline'
  if (status === 'warning') return 'st-warning'
  return 'st-unknown'
}

function statusText(s) {
  return s === 'online' ? '在线' : s === 'offline' ? '离线' : s === 'warning' ? '警告' : '未知'
}

export function buildDeviceHtml({ rows, columns }) {
  const headers = columns.map((c) => `<th>${c.header}</th>`).join('')
  const body = rows
    .map((row) => {
      const tds = columns
        .map((c) => {
          let val = c.format ? c.format(row[c.key]) : row[c.key]
          if (val === null || val === undefined) val = ''
          if (c.key === 'status') {
            return `<td class="${statusClass(row.status)}">${statusText(row.status)}</td>`
          }
          if (c.key === 'image_file') {
            return val
              ? `<td><img src="images/${val}" loading="lazy"></td>`
              : '<td>-</td>'
          }
          return `<td>${String(val).replace(/</g, '&lt;')}</td>`
        })
        .join('')
      return `<tr>${tds}</tr>`
    })
    .join('')
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>设备资产</title>
<style>
  body { font-family: 'Microsoft YaHei', sans-serif; margin: 24px; color: #333; }
  h1 { font-size: 20px; }
  table { border-collapse: collapse; width: 100%; margin-top: 16px; }
  th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; }
  th { background: #f5f7fa; }
  img { width: 90px; height: 60px; object-fit: cover; border-radius: 4px; }
  .st-online { color: #67c23a; font-weight: 600; }
  .st-offline { color: #f56c6c; font-weight: 600; }
  .st-warning { color: #e6a23c; font-weight: 600; }
  .st-unknown { color: #909399; }
</style>
</head>
<body>
<h1>设备资产</h1>
<p>导出时间：${new Date().toLocaleString()}</p>
<table>${headers ? `<thead><tr>${headers}</tr></thead>` : ''}<tbody>${body}</tbody></table>
</body>
</html>`
}

async function fetchImageBlob(row) {
  const res = await fetch(row.image_url)
  if (!res.ok) throw new Error(`fetch failed: ${row.image_url}`)
  return res.blob()
}

export async function buildExportZip({
  rows,
  csvColumns,
  htmlColumns = csvColumns,
  fetchImage = fetchImageBlob,
}) {
  const zip = new JSZip()
  const withImage = rows.map((row) => {
    const file = row.image_url ? imageFileName(row) : ''
    return { ...row, image_file: file }
  })
  await Promise.all(
    withImage.map(async (row) => {
      if (!row.image_file) return
      try {
        const blob = await fetchImage(row)
        zip.file(`images/${row.image_file}`, new Uint8Array(await blob.arrayBuffer()))
      } catch {
        row.image_file = ''
      }
    })
  )
  zip.file('设备资产.csv', toCsv(withImage, csvColumns))
  zip.file('设备资产.html', buildDeviceHtml({ rows: withImage, columns: htmlColumns }))
  return zip.generateAsync({ type: 'blob' })
}
```

**注意**：HTML 中 `type` 列显示的是上游原始值（如 `switch`）。若需中文类型标签，`DeviceTable` 调用时在 `htmlColumns` 中为 `type` 列提供 `format: typeLabel`（见 Task 2 实现）。

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run src/utils/__tests__/exportZip.spec.js`（在 `frontend/`）
Expected: 全部通过（现有 3 + 新增 5）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/exportZip.js frontend/src/utils/__tests__/exportZip.spec.js
git commit -m "feat: add html report to zip export alongside csv"
```

---

### Task 2: DeviceTable 单按钮改造

**Files:**
- Modify: `frontend/src/components/DeviceTable.vue`
- Test: `frontend/src/components/__tests__/DeviceTable.spec.js`

**Interfaces:**
- Consumes: `buildExportZip({ rows, csvColumns, htmlColumns, fetchImage })` 来自 Task 1；`typeLabel`（`frontend/src/utils/deviceTypes.js`）
- Produces: 单一"导出 ZIP"按钮；`onExportZip` 传入 `htmlColumns`（含 `type` 列 `format: typeLabel`、后缀"最近巡检"格式化列）

- [ ] **Step 1: 改 DeviceTable.spec.js**

在文件顶部 `describe('DeviceTable 导出 CSV', ...)` 改为 `describe('DeviceTable 导出 ZIP', ...)`，并替换用例：

```js
describe('DeviceTable 导出 ZIP', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('工具栏只有导出 ZIP 按钮，无导出 CSV 按钮', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const btns = wrapper.findAll('button').map((b) => b.text())
    expect(btns).toContain('导出 ZIP')
    expect(btns).not.toContain('导出 CSV')
  })

  it('有数据时导出并提示条数', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text() === '导出 ZIP')
    await btn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))
    await flushPromises()
    expect(successMock).toHaveBeenCalledWith(expect.stringContaining('已导出'))
  })

  it('无数据时提示无数据可导出', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const input = wrapper.find('input[placeholder*="搜索"]')
    await input.setValue('完全不存在的关键词xyz')
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text() === '导出 ZIP')
    await btn.trigger('click')
    await flushPromises()
    expect(warningMock).toHaveBeenCalledWith('无数据可导出')
  })
})
```

删除原 `describe('DeviceTable 导出 CSV', ...)` 与 `describe('DeviceTable 导出 ZIP', ...)`（注意当前文件已有两个同名 describe，全部收敛为一个）。当前 spec 文件末尾是旧的 ZIP 测试，需要整体替换。

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- --run src/components/__tests__/DeviceTable.spec.js`（在 `frontend/`）
Expected: FAIL — 仍有两个 describe 或旧 CSV 用例断言存在"导出 CSV"失败

- [ ] **Step 3: 改 DeviceTable.vue**

修改 `<script setup>`：移除 `onExport` 函数与"导出 CSV"按钮；`onExportZip` 传入 `htmlColumns`：

```js
const zipColumns = [
  { key: 'type', header: '类型', format: typeLabel },
  ...csvColumns.filter((c) => c.key !== 'type'),
  { key: 'image_file', header: '图片', format: (v) => v || '' },
]

async function onExportZip() {
  const rows = filteredDevices.value
  if (!rows.length) {
    ElMessage.warning('无数据可导出')
    return
  }
  try {
    const blob = await buildExportZip({ rows, csvColumns: zipColumns, htmlColumns: zipColumns })
    downloadCsv(`设备资产_${new Date().toISOString().slice(0, 10)}.zip`, blob)
    ElMessage.success(`已导出 ${rows.length} 条记录`)
  } catch {
    ElMessage.error('导出失败')
  }
}
```

模板中改为只有 `导出 ZIP` 按钮：

```html
<el-button size="small" @click="onExportZip">导出 ZIP</el-button>
```

移除 `csvColumns` 中 `image_file` 列定义内赘余（保持 CSV 列与 HTML 列一致——`zipColumns` 含 `type` 的 `typeLabel` format 且含 `image_file`）。同时更新导出 CSV 按钮删除。

**注意**：原 `onExport` 函数需完整删除；`toCsv` 仍被 `buildExportZip` 内部使用（`exportZip.js`），`DeviceTable` 中不再直接 import `toCsv`（保留 `downloadCsv`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run src/components/__tests__/DeviceTable.spec.js`（在 `frontend/`）
Expected: 全部通过

- [ ] **Step 5: 全量回归 + 构建**

Run: `npm run test`（在 `frontend/`）
Expected: 全过
Run: `npm run build`（在 `frontend/`）
Expected: 构建成功

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/DeviceTable.vue frontend/src/components/__tests__/DeviceTable.spec.js
git commit -m "feat: consolidate device export into single zip button with csv and html"
```

---

### Task 3: 版本号升级到 0.4.2 并发布

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/package.json`

- [ ] **Step 1: 后端版本**

`backend/app/main.py:29`：`app = FastAPI(title="织网 WebWeaver", version="0.4.2", lifespan=lifespan)`

- [ ] **Step 2: 前端版本**

`frontend/package.json`：`"version": "0.4.2"`

- [ ] **Step 3: 提交推送打 tag**

```bash
git add backend/app/main.py frontend/package.json
git commit -m "chore: bump version to 0.4.2"
git tag 0.4.2
git push origin main
git push origin 0.4.2
```

- [ ] **Step 4: 确认 CI 构建成功**

Run（轮询）：`event=push&ref=0.4.2` 直到 `conclusion: success`
Expected: ghcr 镜像 `0.4.2` 出现在 tags list

---

## Self-Review

- **Spec 覆盖**：ZIP 含 CSV+HTML ✅ Task 1；HTML 缩略图/状态色/中文 ✅ Task 1；单按钮/移除 CSV 按钮 ✅ Task 2；错误处理 ✅ Task 1/2；无图 `-` ✅ Task 1。无遗漏。
- **占位符扫描**：全部步骤含真实代码与命令。
- **类型一致性**：`buildExportZip({ rows, csvColumns, htmlColumns, fetchImage })` 在 Task 1/2 签名一致；`buildDeviceHtml({ rows, columns })` 一致；`zipColumns`（含 `image_file` 且 `type` 用 `typeLabel`）在两个 Task 达成一致。HTML 中状态列使用 `row.status` 原始值判断 class，文本用 `statusText`，与 `statusText`（前端组件内同逻辑）一致。