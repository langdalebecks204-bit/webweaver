# 拓扑关系图谱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增"拓扑图"独立 tab，用 2d-force-graph 将设备树渲染为暗黑霓虹风格力导向图谱（发光节点、离线呼吸灯、悬停聚焦、延时粒子流）。

**Architecture:** 纯前端。`treeToGraph.js` 纯函数把 store.tree 打平为 `{nodes, links}`；`TopologyView.vue` 挂载 2d-force-graph 并配置特效；`MainView.vue` 增加 tab 页签。

**Tech Stack:** Vue 3、2d-force-graph、vitest、@vue/test-utils。

## Global Constraints

- 状态色：在线 `#10b981` / 警告 `#f59e0b` / 离线 `#ef4444` / 未知 `#6b7280`
- 背景 `#0f172a`；分组节点强制 status=unknown（灰）
- 节点 `val` = 子设备数 × 3 + 8；半径 `Math.max(4, Math.sqrt(val))`
- 粒子：延时 ≤50 → 2 个 / 50-200 → 1 个 / >200 或 null → 0 个；`linkDirectionalParticleSpeed` 高延时慢
- 悬停聚焦：非高亮节点/边透明度 0.08
- 复用 `useDevicesStore().tree`，无后端改动
- 高度 `calc(100vh - 200px)`；空树显示"暂无设备"

---

### Task 1: `treeToGraph.js` 纯函数与测试

**Files:**
- Create: `frontend/src/utils/treeToGraph.js`
- Test: `frontend/src/utils/__tests__/treeToGraph.spec.js`

**Interfaces:**
- Produces: `treeToGraph(tree)` → `{ nodes, links }`
  - `nodes`: `{ id, name, type, status, latency_ms, ip_address, val }`
  - `links`: `{ source: parentId, target: childId, status }`
  - 分组节点（type=group）status 强制 `'unknown'`；`val` = 子设备数 × 3 + 8

- [ ] **Step 1: 写失败测试**

```js
import { describe, it, expect } from 'vitest'
import { treeToGraph } from '../treeToGraph'

const tree = [
  {
    id: 1, name: '机房A', type: 'group', status: 'online', parent_id: null,
    children: [
      {
        id: 2, name: '核心交换机', type: 'switch', status: 'online',
        latency_ms: 5, ip_address: '10.0.0.1', parent_id: 1, children: [],
      },
      {
        id: 3, name: '终端B', type: 'terminal', status: 'offline',
        latency_ms: null, ip_address: '10.0.0.2', parent_id: 1, children: [],
      },
    ],
  },
]

describe('treeToGraph', () => {
  it('树打平为节点与链接', () => {
    const { nodes, links } = treeToGraph(tree)
    expect(nodes.map((n) => n.id).sort()).toEqual([1, 2, 3])
    expect(links).toContainEqual({ source: 1, target: 2, status: 'online' })
    expect(links).toContainEqual({ source: 1, target: 3, status: 'offline' })
  })

  it('分组节点状态强制 unknown 且权重随子节点数', () => {
    const { nodes } = treeToGraph(tree)
    const group = nodes.find((n) => n.id === 1)
    expect(group.status).toBe('unknown')
    expect(group.val).toBe(2 * 3 + 8) // 2 个子设备
    const leaf = nodes.find((n) => n.id === 2)
    expect(leaf.val).toBe(8)
  })

  it('空树返回空', () => {
    expect(treeToGraph([])).toEqual({ nodes: [], links: [] })
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- --run src/utils/__tests__/treeToGraph.spec.js`（在 `frontend/`）
Expected: FAIL — Cannot find module '../treeToGraph'

- [ ] **Step 3: 写实现**

```js
export function treeToGraph(tree) {
  const nodes = []
  const links = []
  function walk(items, parentId = null) {
    for (const node of items) {
      const childCount = node.children ? node.children.length : 0
      nodes.push({
        id: node.id,
        name: node.name,
        type: node.type,
        status: node.type === 'group' ? 'unknown' : node.status || 'unknown',
        latency_ms: node.latency_ms ?? null,
        ip_address: node.ip_address || '',
        val: childCount * 3 + 8,
      })
      if (parentId !== null) {
        links.push({ source: parentId, target: node.id, status: node.status || 'unknown' })
      }
      if (childCount > 0) walk(node.children, node.id)
    }
  }
  walk(tree)
  return { nodes, links }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run src/utils/__tests__/treeToGraph.spec.js`（在 `frontend/`）
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/treeToGraph.js frontend/src/utils/__tests__/treeToGraph.spec.js
git commit -m "feat: add treeToGraph conversion utility"
```

---

### Task 2: TopologyView.vue 组件（含特效）

**Files:**
- Create: `frontend/src/components/TopologyView.vue`
- Test: `frontend/src/components/__tests__/TopologyView.spec.js`

**Interfaces:**
- Consumes: `treeToGraph(tree)` 来自 Task 1；`useDevicesStore()`（pinia，`.tree`）
- Produces: `TopologyView.vue` 默认导出组件，无 props，独立渲染图谱

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/components/__tests__/TopologyView.spec.js`：

```js
// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mount } from '@vue/test-utils'

const graphDataMock = vi.fn()
const hoverMock = vi.fn()
const createMock = vi.fn(() => ({
  graphData: graphDataMock,
  onNodeHover: hoverMock,
  nodeCanvasObject: vi.fn(),
  nodeCanvasObjectMode: vi.fn(),
  backgroundColor: vi.fn(),
  linkDirectionalParticles: vi.fn(),
  linkDirectionalParticleSpeed: vi.fn(),
  linkDirectionalParticleWidth: vi.fn(),
  linkDirectionalParticleColor: vi.fn(),
  width: vi.fn(),
  height: vi.fn(),
}))

vi.mock('2d-force-graph', () => ({ default: createMock }))

const treeMock = vi.hoisted(() => [
  { id: 1, name: '机房A', type: 'group', status: 'online', parent_id: null, children: [] },
])

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({ tree: treeMock }),
}))

import TopologyView from '../TopologyView.vue'

describe('TopologyView', () => {
  it('挂载时创建图谱并设置数据', async () => {
    mount(TopologyView)
    await flushPromises()
    expect(createMock).toHaveBeenCalled()
    expect(graphDataMock).toHaveBeenCalled()
  })

  it('空树时显示空态提示', async () => {
    treeMock.splice(0, treeMock.length)
    const wrapper = mount(TopologyView)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无设备')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- --run src/components/__tests__/TopologyView.spec.js`（在 `frontend/`）
Expected: FAIL — Cannot find module '../TopologyView.vue'

- [ ] **Step 3: 安装依赖**

Run: `npm install 2d-force-graph`（在 `frontend/`）
Expected: package.json 新增 `"2d-force-graph"`

- [ ] **Step 4: 写实现**

创建 `frontend/src/components/TopologyView.vue`：

```vue
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ForceGraph from '2d-force-graph'
import { useDevicesStore } from '../stores/devices'
import { treeToGraph } from '../utils/treeToGraph'

const store = useDevicesStore()
const graphEl = ref(null)
const error = ref('')
const hoverNodeId = ref(null)

const graphData = computed(() => treeToGraph(store.tree))

const STATUS_COLORS = {
  online: '#10b981',
  warning: '#f59e0b',
  offline: '#ef4444',
  unknown: '#6b7280',
}

let fg = null

function particleCount(link) {
  const target = link.target
  const lat = target.latency_ms
  if (lat == null) return 0
  if (lat <= 50) return 2
  if (lat <= 200) return 1
  return 0
}

function particleSpeed(link) {
  const lat = link.target.latency_ms
  if (lat == null) return 0
  if (lat <= 50) return 0.02
  if (lat <= 200) return 0.01
  return 0.005
}

function particleColor(link) {
  const lat = link.target.latency_ms
  if (lat == null) return '#6b7280'
  if (lat <= 50) return '#34d399'
  if (lat <= 200) return '#fbbf24'
  return '#ef4444'
}

function isHighlighted(node) {
  if (hoverNodeId.value == null) return true
  if (node.id === hoverNodeId.value) return true
  const adjacent = graphData.value.links.some(
    (l) =>
      (l.source.id === hoverNodeId.value && l.target.id === node.id) ||
      (l.target.id === hoverNodeId.value && l.source.id === node.id)
  )
  return adjacent
}

function drawNode(node, ctx) {
  const r = Math.max(4, Math.sqrt(node.val))
  const color = STATUS_COLORS[node.status] || '#6b7280'
  const now = Date.now()
  let alpha = isHighlighted(node) ? 1 : 0.08
  if (node.status === 'offline' && isHighlighted(node)) {
    alpha = 0.5 + 0.5 * Math.abs(Math.sin(now / 500))
  }
  ctx.globalAlpha = alpha
  ctx.beginPath()
  ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false)
  ctx.fillStyle = color
  ctx.shadowColor = color
  ctx.shadowBlur = node.status === 'unknown' ? 4 : 14
  ctx.fill()
  ctx.shadowBlur = 0
  ctx.globalAlpha = 1
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.font = '12px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(node.name, node.x, node.y - r - 4)
}

function renderGraph() {
  if (!graphEl.value) return
  if (fg) fg.destroy()
  fg = ForceGraph(graphEl.value)
    .backgroundColor('#0f172a')
    .graphData(graphData.value)
    .nodeRelSize(1)
    .nodeCanvasObjectMode(() => 'replace')
    .nodeCanvasObject(drawNode)
    .linkColor(() => 'rgba(148,163,184,0.6)')
    .linkDirectionalParticles(particleCount)
    .linkDirectionalParticleSpeed(particleSpeed)
    .linkDirectionalParticleWidth(2)
    .linkDirectionalParticleColor(particleColor)
    .onNodeHover((node) => {
      hoverNodeId.value = node ? node.id : null
      if (node) {
        fg.graphData(graphData.value)
      }
    })
    .width(graphEl.value.clientWidth)
    .height(graphEl.value.clientHeight)
}

onMounted(() => {
  try {
    renderGraph()
  } catch (e) {
    error.value = `图谱初始化失败：${e.message}`
  }
})

onBeforeUnmount(() => {
  if (fg) {
    fg.destroy()
    fg = null
  }
})
</script>

<template>
  <div class="topology-wrap">
    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="!graphData.nodes.length" class="empty">暂无设备</div>
    <div v-else ref="graphEl" class="graph" />
  </div>
</template>

<style scoped>
.topology-wrap {
  width: 100%;
  height: calc(100vh - 200px);
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}
.graph {
  width: 100%;
  height: 100%;
}
.error {
  color: #ef4444;
  padding: 24px;
}
.empty {
  color: #94a3b8;
  padding: 24px;
}
</style>
```

**注意**：
- 悬停刷新用 `fg.graphData(graphData.value)` 触发重绘（简化实现：hover 时整图数据重设以驱动透明度变化）
- `nodeCanvasObject` 每帧执行，离线呼吸灯基于 `Date.now()` 实现
- 组件无 props，直接消费 store

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- --run src/components/__tests__/TopologyView.spec.js`（在 `frontend/`）
Expected: 2 passed（空态测试需调整——见 Step 6 说明）

**说明**：空态测试中 `treeMock.splice` 会在两次 mount 间清空共享 mock 树，若第二个测试因前一个测试副作用失败，改为独立清空方式。如遇问题，将空树逻辑改为 `graphData.nodes.length === 0` 判空，并在测试文件顶部为每个测试重建 `treeMock`（用 `beforeEach` 重置）。

- [ ] **Step 6: 提交**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/TopologyView.vue frontend/src/components/__tests__/TopologyView.spec.js
git commit -m "feat: add dark neon topology graph view with effects"
```

---

### Task 3: MainView 增加"拓扑图"tab

**Files:**
- Modify: `frontend/src/views/MainView.vue`
- Test: `frontend/src/views/__tests__/MainView.spec.js`

**Interfaces:**
- Consumes: `TopologyView` 组件（Task 2）
- Produces: 顶部 tab 增加 `name="topology"` 页签

- [ ] **Step 1: 写失败测试（MainView.spec.js 追加用例）**

在 `frontend/src/views/__tests__/MainView.spec.js` 的现有 describe 内追加：

```js
it('包含拓扑图 tab', async () => {
  const wrapper = mount(MainView)
  await flushPromises()
  const tabs = wrapper.findAll('.el-tabs__item').map((t) => t.text())
  expect(tabs).toContain('拓扑图')
})
```

（该 spec 的现有 mock 结构需包含 `TopologyView` 的 stub，见 Step 2 失败后的调整说明。）

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- --run src/views/__tests__/MainView.spec.js`（在 `frontend/`）
Expected: FAIL — 找不到"拓扑图"tab；若因 TopologyView 真实渲染导致（2d-force-graph 在 happy-dom 无 canvas），需在 MainView.spec.js 顶部加 stub：

```js
vi.mock('../../components/TopologyView.vue', () => ({
  default: { name: 'TopologyView', template: '<div class="topology-stub" />' },
}))
```

（若原本就有全局组件 stub 机制，按该机制处理。）

- [ ] **Step 3: 修改 MainView.vue**

script 区 import：

```js
import TopologyView from '../components/TopologyView.vue'
```

`<el-tabs>` 内、"设备"页签后追加：

```html
<el-tab-pane label="拓扑图" name="topology">
  <el-card><TopologyView /></el-card>
</el-tab-pane>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run src/views/__tests__/MainView.spec.js`（在 `frontend/`）
Expected: 全部通过

- [ ] **Step 5: 全量回归 + 构建**

Run: `npm run test`（在 `frontend/`）
Expected: 全过
Run: `npm run build`（在 `frontend/`）
Expected: 构建成功

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/MainView.vue frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: add topology graph tab to main view"
```

---

### Task 4: 版本号升级到 0.4.3 并发布

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/package.json`

- [ ] **Step 1: 后端版本**

`backend/app/main.py:29`：`app = FastAPI(title="织网 WebWeaver", version="0.4.3", lifespan=lifespan)`

- [ ] **Step 2: 前端版本**

`frontend/package.json`：`"version": "0.4.3"`

- [ ] **Step 3: 提交推送打 tag**

```bash
git add backend/app/main.py frontend/package.json
git commit -m "chore: bump version to 0.4.3"
git tag 0.4.3
git push origin main
git push origin 0.4.3
```

- [ ] **Step 4: 确认 CI 构建成功**

Run（轮询）：`event=push&ref=0.4.3` 直到 `conclusion: success`
Expected: ghcr 镜像 `0.4.3` 出现在 tags list

---

## Self-Review

- **Spec 覆盖**：基础力导向图 ✅ Task 2；霓虹发光/呼吸灯/悬停聚焦/粒子流/节点权重 ✅ Task 2；分组节点 unknown ✅ Task 1；独立 tab ✅ Task 3；空态/错误处理 ✅ Task 2；无后端改动 ✅。无遗漏。
- **占位符扫描**：全部步骤含真实代码与命令。
- **类型一致性**：`treeToGraph(tree)` → `{nodes, links}` 在 Task 1/2 签名一致；节点字段 `id/name/type/status/latency_ms/ip_address/val` 两处一致；links `{source, target, status}` 一致。`ForceGraph(domEl)` 用法与 2d-force-graph API 匹配。