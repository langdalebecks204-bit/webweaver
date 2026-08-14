# 设备资产 ZIP 导出（含图片） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在设备表格页新增"导出 ZIP"按钮，将当前筛选设备打包为含 CSV 清单与图片文件夹的 ZIP 供下载。

**Architecture:** 纯前端实现。新增 jszip 依赖；新建 `exportZip.js` 提供 `buildExportZip({ rows, csvColumns, fetchImage })` 纯函数，用 jszip 生成 ZIP Blob；`DeviceTable.vue` 增加 `onExportZip` 与独立按钮，图片按 `设备名_设备id.jpg` 命名存入 `images/`，无图设备不进 ZIP 且 CSV"图片"列留空。

**Tech Stack:** Vue 3 (script setup)、jszip、vitest + @vue/test-utils、element-plus。

## Global Constraints

- 图片命名格式：`images/{name}_{id}.jpg`（如 `核心交换机_12.jpg`）
- 图片文件名需做非法字符替换（`\ / : * ? " < > |` → `_`）
- 单张图片 fetch 失败必须跳过不中断，且该行 CSV"图片"列留空
- 无数据时沿用 `ElMessage.warning('无数据可导出')`
- CSV 导出（"导出 CSV"按钮）行为不变，不增加"图片"列
- 复用现有 `toCsv`/`downloadCsv`（`frontend/src/utils/csv.js`）

---

### Task 1: 安装 jszip 并写 `exportZip.js` 纯函数与测试

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/utils/exportZip.js`
- Test: `frontend/src/utils/__tests__/exportZip.spec.js`

**Interfaces:**
- Produces: `buildExportZip({ rows, csvColumns, fetchImage })` → `Promise<Blob>`
  - `rows`: 设备数组，每项含 `id`、`name`、`image_url`（`/uploads/{id}.jpg` 或 null）
  - `csvColumns`: `{ key, header, format? }[]`，传给 `toCsv`
  - `fetchImage(row)`：返回 `Promise<Blob>`，默认 `fetch(row.image_url).then(r => r.blob())`
  - 返回 ZIP Blob；有图设备写入 `images/{name}_{id}.jpg`，CSV 中 `image_file` 键为文件名（含换名规则），无图设备 `image_file` 为 `''`

- [ ] **Step 1: 安装 jszip**

Run: `npm install jszip`（在 `frontend/` 目录）
Expected: package.json 新增 `"jszip"` 依赖

- [ ] **Step 2: 写失败测试 `frontend/src/utils/__tests__/exportZip.spec.js`**

```js
import { describe, it, expect } from 'vitest'
import JSZip from 'jszip'
import { buildExportZip } from '../exportZip'

const rows = [
  {
    id: 12,
    name: '核心交换机',
    type: 'switch',
    ip_address: '10.0.0.1',
    image_url: '/uploads/12.jpg',
  },
  { id: 13, name: '终端B', type: 'terminal', ip_address: '10.0.0.2', image_url: null },
]

const columns = [
  { key: 'name', header: '名称' },
  { key: 'ip_address', header: 'IP' },
  { key: 'image_file', header: '图片' },
]

async function readZip(blob) {
  return JSZip.loadAsync(await blob.arrayBuffer())
}

describe('buildExportZip', () => {
  it('打包 CSV 与图片，命名正确，无图设备图片列留空', async () => {
    const fetchImage = vi.fn(async (row) => new Blob(['jpg-bytes-12'], { type: 'image/jpeg' }))
    const blob = await buildExportZip({ rows, csvColumns: columns, fetchImage })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).toContain('设备资产.csv')
    expect(Object.keys(zip.files)).toContain('images/核心交换机_12.jpg')
    expect(Object.keys(zip.files)).not.toContain('images/终端B_13.jpg')
    const csv = await zip.file('设备资产.csv').async('string')
    expect(csv).toContain('核心交换机,10.0.0.1,images/核心交换机_12.jpg')
    expect(csv).toContain('终端B,10.0.0.2,')
    const img = await zip.file('images/核心交换机_12.jpg').async('arraybuffer')
    expect(new TextDecoder().decode(img)).toBe('jpg-bytes-12')
    expect(fetchImage).toHaveBeenCalledTimes(1)
  })

  it('图片 fetch 失败时跳过该图且 CSV 留空，不抛异常', async () => {
    const fetchImage = vi.fn(async () => { throw new Error('network') })
    const blob = await buildExportZip({ rows, csvColumns: columns, fetchImage })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).not.toContain('images/核心交换机_12.jpg')
    const csv = await zip.file('设备资产.csv').async('string')
    expect(csv).toContain('核心交换机,10.0.0.1,')
  })

  it('图片文件名中的非法字符替换为下划线', async () => {
    const weird = [{ id: 1, name: 'A/B:C*D', image_url: '/uploads/1.jpg' }]
    const fetchImage = vi.fn(async () => new Blob(['x']))
    const blob = await buildExportZip({ rows: weird, csvColumns: columns, fetchImage })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).toContain('images/A_B_C_D_1.jpg')
  })
})
```

- [ ] **Step 3: 运行测试确认失败**

Run: `npm run test -- --run src/utils/__tests__/exportZip.spec.js`（在 `frontend/`）
Expected: FAIL — "Cannot find module '../exportZip'"

- [ ] **Step 4: 写实现 `frontend/src/utils/exportZip.js`**

```js
import JSZip from 'jszip'
import { toCsv } from './csv'

const ILLEGAL = /[\\/:*?"<>|]/g

export function imageFileName(row) {
  return `${String(row.name).replace(ILLEGAL, '_')}_${row.id}.jpg`
}

async function fetchImageBlob(row) {
  const res = await fetch(row.image_url)
  if (!res.ok) throw new Error(`fetch failed: ${row.image_url}`)
  return res.blob()
}

export async function buildExportZip({ rows, csvColumns, fetchImage = fetchImageBlob }) {
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
  return zip.generateAsync({ type: 'blob' })
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- --run src/utils/__tests__/exportZip.spec.js`（在 `frontend/`）
Expected: 3 passed

- [ ] **Step 6: 提交**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/utils/exportZip.js frontend/src/utils/__tests__/exportZip.spec.js
git commit -m "feat: add zip export utility bundling device csv and images"
```

---

### Task 2: DeviceTable 集成"导出 ZIP"按钮

**Files:**
- Modify: `frontend/src/components/DeviceTable.vue`（script 部分新增 onExportZip；template 工具栏加按钮）
- Test: `frontend/src/components/__tests__/DeviceTable.spec.js`

**Interfaces:**
- Consumes: `buildExportZip({ rows, csvColumns, fetchImage })` 来自 Task 1
- Uses: 现有 `downloadCsv(filename, content)`（`frontend/src/utils/csv.js`），其 `content` 为 Blob 时直接作为下载内容
- Produces: `onExportZip()`：无数据 `ElMessage.warning('无数据可导出')`；成功 `ElMessage.success('已导出 N 条记录')`；异常 `ElMessage.error('导出失败')`

- [ ] **Step 1: 写失败测试（DeviceTable.spec.js 追加 describe）**

在 `frontend/src/components/__tests__/DeviceTable.spec.js` 文件末尾追加：

```js
describe('DeviceTable 导出 ZIP', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('有数据时导出并提示条数', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text() === '导出 ZIP')
    expect(btn).toBeTruthy()
    await btn.trigger('click')
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

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- --run src/components/__tests__/DeviceTable.spec.js`（在 `frontend/`）
Expected: FAIL — 找不到"导出 ZIP"按钮

- [ ] **Step 3: 修改 DeviceTable.vue**

在 `<script setup>` 中追加（import 区加 `import { buildExportZip } from '../utils/exportZip'`）：

```js
const zipColumns = [
  ...csvColumns,
  { key: 'image_file', header: '图片', format: (v) => v || '' },
]

async function onExportZip() {
  const rows = filteredDevices.value
  if (!rows.length) {
    ElMessage.warning('无数据可导出')
    return
  }
  try {
    const blob = await buildExportZip({ rows, csvColumns: zipColumns })
    downloadCsv(`设备资产_${new Date().toISOString().slice(0, 10)}.zip`, blob)
    ElMessage.success(`已导出 ${rows.length} 条记录`)
  } catch {
    ElMessage.error('导出失败')
  }
}
```

在 `<template>` 工具栏（第 100 行"导出 CSV"按钮旁）追加：

```html
<el-button size="small" @click="onExportZip">导出 ZIP</el-button>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run src/components/__tests__/DeviceTable.spec.js`（在 `frontend/`）
Expected: 全过（原 6 + 新增 2 = 8 passed）

- [ ] **Step 5: 全量前端回归 + 构建**

Run: `npm run test`（在 `frontend/`）
Expected: 全过
Run: `npm run build`（在 `frontend/`）
Expected: 构建成功

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/DeviceTable.vue frontend/src/components/__tests__/DeviceTable.spec.js
git commit -m "feat: add export ZIP button to device table"
```

---

### Task 3: 版本号升级到 0.4.1 并发布

**Files:**
- Modify: `backend/app/main.py`（FastAPI `version`）
- Modify: `frontend/package.json`（`"version"`）

**Interfaces:**
- Consumes: Task 1、Task 2 的代码变更已提交

- [ ] **Step 1: 修改后端版本号**

`backend/app/main.py:29`：`app = FastAPI(title="织网 WebWeaver", version="0.4.1", lifespan=lifespan)`

- [ ] **Step 2: 修改前端版本号**

`frontend/package.json`：`"version": "0.4.1"`

- [ ] **Step 3: 提交并打 tag 推送**

```bash
git add backend/app/main.py frontend/package.json
git commit -m "chore: bump version to 0.4.1"
git tag 0.4.1
git push origin main
git push origin 0.4.1
```

- [ ] **Step 4: 确认 CI 构建成功**

Run（轮询 GitHub Actions，`event=push&ref=0.4.1`）：等待 `conclusion: success`
Expected: ghcr 镜像 `0.4.1` 出现（`ghcr.io/v2/.../tags/list`）

---

## Self-Review

- **Spec 覆盖**：导出范围=当前筛选 ✅ Task 2 `onExportZip` 用 `filteredDevices`；图片命名 ✅ Task 1 `imageFileName`；无图留空/不进 images ✅ Task 1 测试；fetch 失败跳过 ✅ Task 1 测试；UI 独立按钮 ✅ Task 2；错误处理 ✅ Task 2。无遗漏。
- **占位符扫描**：全部步骤含真实代码与命令。
- **类型一致性**：`buildExportZip({ rows, csvColumns, fetchImage })` 在 Task 1/2 中签名一致；`imageFileName` 输出 `{name}_{id}.jpg` 且与 CSV `image_file` 值一致；`downloadCsv` 接受 Blob 与现有 `text/csv` Blob 创建方式兼容（zip Blob 可直接下载）。
