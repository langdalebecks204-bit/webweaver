# 拓扑图全屏与体验优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 拓扑图支持页面内全屏（含返回主页链接）、停止反复重排版（保留拖拽摆位）、节点改为大圆点+设备类型图标、标签字号默认最小。

**Architecture:** 全部改动集中在 `TopologyView.vue`、`MainView.vue`（接线 back-home 事件）与 `utils/deviceTypes.js`（新增 typeGlyph 纯函数）。全屏用浏览器 Fullscreen API + `:fullscreen` CSS；防重排通过按 id 复用 force-graph 节点对象实现。

**Tech Stack:** Vue 3 `<script setup>`、Element Plus、force-graph、vitest + happy-dom、@vue/test-utils。

## Global Constraints

- 设计规格：`docs/superpowers/specs/2026-08-24-topology-fullscreen-design.md`
- 测试命令：在 `frontend/` 目录 `npx vitest run`；单文件 `npx vitest run <path>`
- 构建验证：`npm run build`
- 不引入新依赖；不改 Element Plus 图标体系（DEVICE_TYPE_ICONS 保持不动）
- 提交信息用 conventional commits（feat:/test:/docs:）
- 现有 TopologyView 用例除明确指出的断言外不得破坏

---

### Task 1: deviceTypes.js 新增 DEVICE_TYPE_GLYPHS 与 typeGlyph

**Files:**
- Modify: `frontend/src/utils/deviceTypes.js`
- Test: `frontend/src/utils/__tests__/deviceTypes.spec.js`

**Interfaces:**
- Produces: `DEVICE_TYPE_GLYPHS`（Record<string,string> emoji 表）、`typeGlyph(type?: string): string`。后续 Task 3 在 drawNode 中调用 `typeGlyph(node.type)`。

- [ ] **Step 1: Write the failing test**

在 `frontend/src/utils/__tests__/deviceTypes.spec.js` 末尾追加：

```js
describe('typeGlyph 拓扑节点图标', () => {
  it('内置类型返回对应 emoji', () => {
    expect(typeGlyph('group')).toBe('📁')
    expect(typeGlyph('switch')).toBe('🔀')
    expect(typeGlyph('unmanaged_switch')).toBe('🔌')
    expect(typeGlyph('ups')).toBe('🔋')
  })
  it('自定义类型返回类型名首字', () => {
    expect(typeGlyph('打印机房')).toBe('打')
  })
  it('未知或空类型返回问号', () => {
    expect(typeGlyph('')).toBe('?')
    expect(typeGlyph()).toBe('?')
  })
})
```

并在该文件顶部 import 处加入 `typeGlyph`（与现有 import 合并）。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend; npx vitest run src/utils/__tests__/deviceTypes.spec.js`
Expected: FAIL — `typeGlyph` 未导出（import 报错或 undefined）

- [ ] **Step 3: Write minimal implementation**

在 `frontend/src/utils/deviceTypes.js` 的 `DEFAULT_TYPE_ICON` 之后追加：

```js
export const DEVICE_TYPE_GLYPHS = {
  group: '📁',
  server: '🖥️',
  switch: '🔀',
  terminal: '💻',
  camera: '📷',
  nvr: '🎛️',
  router: '📡',
  firewall: '🛡️',
  ap: '📶',
  printer: '🖨️',
  nas: '💾',
  ups: '🔋',
  unmanaged_switch: '🔌',
}

export function typeGlyph(type) {
  if (DEVICE_TYPE_GLYPHS[type]) return DEVICE_TYPE_GLYPHS[type]
  if (type) return typeLabel(type)[0] || '?'
  return '?'
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend; npx vitest run src/utils/__tests__/deviceTypes.spec.js`
Expected: PASS（全部用例）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/deviceTypes.js frontend/src/utils/__tests__/deviceTypes.spec.js
git commit -m "feat: add type glyph mapping for topology nodes"
```

---

### Task 2: 默认字号最小值

**Files:**
- Modify: `frontend/src/components/TopologyView.vue:11`
- Test: `frontend/src/components/__tests__/TopologyView.spec.js:134`

**Interfaces:**
- Consumes: 无
- Produces: `labelFontSize` 初始值为 6（Task 3 的绘制测试依赖此默认）

- [ ] **Step 1: Update the failing assertion**

`TopologyView.spec.js` 中「标签字号可调整且影响绘制」用例首段断言改为：

```js
expect(ctx.font).toBe('6px sans-serif')
```

（其余断言不动：改字号后仍为 `'14px sans-serif'`。）

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: FAIL — 实际为 `9px sans-serif`

- [ ] **Step 3: Implement**

`TopologyView.vue` 第 11 行：

```js
const labelFontSize = ref(6)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TopologyView.vue frontend/src/components/__tests__/TopologyView.spec.js
git commit -m "feat: default topology label font size to minimum"
```

---

### Task 3: 大圆点 + 类型图标绘制

**Files:**
- Modify: `frontend/src/components/TopologyView.vue`（drawNode 及 import）
- Test: `frontend/src/components/__tests__/TopologyView.spec.js`

**Interfaces:**
- Consumes: `typeGlyph(type)`（Task 1）
- Produces: 半径公式 `Math.max(8, Math.sqrt(node.val))`；图标以 `ctx.fillText(glyph, x, y)` 绘制（`textBaseline='middle'`）

- [ ] **Step 1: Write the failing test**

`TopologyView.spec.js` 追加用例：

```js
it('节点为大圆点并居中绘制类型图标', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  const draw = fgMock.nodeCanvasObject.mock.calls[0][0]
  const ctx = {
    fillStyle: '', font: '', textAlign: '', textBaseline: '',
    fillText: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(),
    globalAlpha: 1, shadowColor: '', shadowBlur: 0,
  }
  const node = { id: 3, name: '核心交换机', type: 'switch', status: 'online', val: 8, x: 50, y: 60 }
  draw(node, ctx)
  expect(ctx.arc).toHaveBeenCalledWith(50, 60, 8, 0, 2 * Math.PI, false)
  expect(ctx.textBaseline).toBe('middle')
  expect(ctx.fillText).toHaveBeenCalledWith('🔀', 50, 60)
})
```

注意：现有各用例的 node 对象需补 `type` 字段（如 `type: 'group'`），否则 `fillText` 收到 `'?'` —— 「隐藏标签时非悬停节点不显示文字」与「标签字号可调整」两个用例的 node 加 `type: 'terminal'` 即可（它们不断言 glyph 内容，不受影响，但保持数据真实）。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: FAIL — `arc` 半径为 4、无 textBaseline/glyph 断言不满足

- [ ] **Step 3: Implement drawNode**

`TopologyView.vue` script 顶部 import 增加：

```js
import { typeGlyph } from '../utils/deviceTypes'
```

`drawNode` 改为（仅列出改动行）：

```js
function drawNode(node, ctx) {
  const r = Math.max(8, Math.sqrt(node.val))
```

圆点 `ctx.fill()` 与 `ctx.shadowBlur = 0` 之后插入图标绘制：

```js
  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.font = '10px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(typeGlyph(node.type), node.x, node.y)
  ctx.textBaseline = 'alphabetic'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: PASS（含既有用例）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TopologyView.vue frontend/src/components/__tests__/TopologyView.spec.js
git commit -m "feat: larger topology nodes with device type glyphs"
```

---

### Task 4: 停止重排版（悬停不重置 + 刷新复用节点坐标）

**Files:**
- Modify: `frontend/src/components/TopologyView.vue`（onNodeHover 链、renderGraph 尾部 watch 区域、新增 syncGraphData）
- Test: `frontend/src/components/__tests__/TopologyView.spec.js`

**Interfaces:**
- Consumes: `graphData` computed（现有）、`fg` 模块级变量（现有）
- Produces: `syncGraphData()`——按 id 复用旧节点对象（Object.assign 更新 name/type/status/latency_ms/ip_address/val），重建 links；watch 从「nodes.length」改为监听整个 `graphData`

- [ ] **Step 1: Write the failing tests**

`TopologyView.spec.js` 追加：

```js
it('悬停节点不重置图数据', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  const before = fgMock.graphData.mock.calls.length
  fgMock.onNodeHover.mock.calls[0][0]({ id: 1 })
  await flushPromises()
  expect(fgMock.graphData.mock.calls.length).toBe(before)
})

it('轮询刷新时复用节点对象保留坐标', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  const first = fgMock.graphData.mock.calls[0][0]
  first.nodes[0].x = 123
  first.nodes[0].y = -45
  store().tree[0].status = 'offline'
  await flushPromises()
  const last = fgMock.graphData.mock.calls.at(-1)[0]
  expect(last.nodes[0]).toBe(first.nodes[0])
  expect(last.nodes[0].x).toBe(123)
  expect(last.nodes[0].status).toBe('offline')
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: 两条均 FAIL（悬停导致 graphData 多调一次；刷新后是新对象引用）

- [ ] **Step 3: Implement**

`TopologyView.vue`：

(a) onNodeHover 移除数据重置：

```js
    .onNodeHover((node) => {
      hoverNodeId.value = node ? node.id : null
    })
```

(b) renderGraph 内 `if (fg)` 早退分支删除（合并逻辑移交 syncGraphData），即删除：

```js
  if (fg) {
    fg.graphData(graphData.value)
    return
  }
```

(c) 新增 syncGraphData（放在 renderGraph 之后）：

```js
const NODE_FIELDS = ['name', 'type', 'status', 'latency_ms', 'ip_address', 'val']

function syncGraphData() {
  if (!fg || !graphData.value.nodes.length) return
  const prevNodes = fg.graphData().nodes || []
  const byId = new Map(prevNodes.map((n) => [n.id, n]))
  const nodes = graphData.value.nodes.map((n) => {
    const old = byId.get(n.id)
    if (old) {
      for (const f of NODE_FIELDS) old[f] = n[f]
      return old
    }
    return { ...n }
  })
  const links = graphData.value.links.map((l) => ({ source: l.source, target: l.target }))
  fg.graphData({ nodes, links })
}
```

(d) watch 改为监听整个 graphData 并走 sync 路径：

```js
watch(
  graphData,
  async () => {
    if (!graphData.value.nodes.length) return
    await nextTick()
    try {
      if (fg) syncGraphData()
      else renderGraph()
    } catch (e) {
      error.value = `图谱初始化失败：${e.message}`
    }
  }
)
```

注意 mock 兼容：`fgMock.graphData()` 无参调用返回 fgMock（vi.fn(() => fgMock)），`prevNodes` 将是 fgMock 本身，`.nodes` 为 undefined → `|| []` 已兜底；但「轮询刷新时复用节点对象保留坐标」用例需要 mock 能存取数据。将该 mock 改为带存储的实现：

```js
let graphStore = { nodes: [], links: [] }
// beforeEach 内：
graphStore = { nodes: [], links: [] }
fgMock = {
  // ...
  graphData: vi.fn((data) => {
    if (data) graphStore = data
    return graphStore
  }),
}
```

（原 `graphData: vi.fn(() => fgMock)` 替换为此实现；链式创建时 `.graphData(graphData.value)` 存入初始数据，语义不变，现有断言 `toHaveBeenCalledTimes` 不受影响。）

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: PASS（全部用例）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TopologyView.vue frontend/src/components/__tests__/TopologyView.spec.js
git commit -m "fix: stop topology relayout on hover and polling refresh"
```

---

### Task 5: 页面内全屏按钮与返回主页链接

**Files:**
- Modify: `frontend/src/components/TopologyView.vue`（template/style/script）
- Modify: `frontend/src/views/MainView.vue:377`（TopologyView 接线 @back-home）
- Test: `frontend/src/components/__tests__/TopologyView.spec.js`
- Test: `frontend/src/views/__tests__/MainView.spec.js`

**Interfaces:**
- Consumes: 无新依赖
- Produces: TopologyView emits `back-home`（无参数）；MainView 收到后 `activeTab = 'devices'`

- [ ] **Step 1: Write the failing tests**

`TopologyView.spec.js` 追加：

```js
it('点击全屏按钮请求全屏，进入全屏后显示返回主页链接', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  const wrapEl = wrapper.find('.topology-wrap').element
  const reqSpy = vi.fn()
  wrapEl.requestFullscreen = reqSpy
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    get: () => null,
  })
  expect(wrapper.find('.back-home').exists()).toBe(false)
  await wrapper.find('.fullscreen-btn').trigger('click')
  expect(reqSpy).toHaveBeenCalledTimes(1)
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    get: () => wrapEl,
  })
  document.dispatchEvent(new Event('fullscreenchange'))
  await flushPromises()
  expect(wrapper.find('.back-home').exists()).toBe(true)
})

it('返回主页退出全屏并向外发出 back-home', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  const wrapEl = wrapper.find('.topology-wrap').element
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    get: () => wrapEl,
  })
  document.dispatchEvent(new Event('fullscreenchange'))
  await flushPromises()
  const exitSpy = vi.fn()
  document.exitFullscreen = exitSpy
  await wrapper.find('.back-home').trigger('click')
  expect(exitSpy).toHaveBeenCalledTimes(1)
  expect(wrapper.emitted('back-home')).toBeTruthy()
})
```

`MainView.spec.js`：将 stub 改为可发事件并追加用例（stub 行替换）：

```js
        TopologyView: {
          emits: ['back-home'],
          template:
            '<div class="topology-stub" @click="$emit(\'back-home\')" />',
        },
```

「MainView 拓扑图页签」describe 追加：

```js
  it('拓扑页返回主页切回设备页签', async () => {
    const wrapper = mountView()
    await flushPromises()
    wrapper.vm.activeTab = 'topology'
    await flushPromises()
    await wrapper.find('.topology-stub').trigger('click')
    expect(wrapper.vm.activeTab).toBe('devices')
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js src/views/__tests__/MainView.spec.js`
Expected: 新用例 FAIL（找不到 .fullscreen-btn / .back-home / activeTab 不变）；MainView 既有用例不受影响

- [ ] **Step 3: Implement TopologyView**

script setup 增加与修改：

```js
const emit = defineEmits(['back-home'])
const wrapEl = ref(null)
const isFullscreen = ref(false)

function toggleFullscreen() {
  const el = wrapEl.value
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

function onFsChange() {
  isFullscreen.value = document.fullscreenElement === wrapEl.value
}

function backHome() {
  if (document.fullscreenElement) document.exitFullscreen?.()
  emit('back-home')
}
```

onMounted 里追加 `document.addEventListener('fullscreenchange', onFsChange)`；
onBeforeUnmount 里追加 `document.removeEventListener('fullscreenchange', onFsChange)`。

template 根元素与工具栏、悬浮链接改为：

```html
  <div ref="wrapEl" class="topology-wrap" :class="{ fullscreen: isFullscreen }">
    <div v-if="error" class="error">{{ error }}</div>
    <template v-else-if="graphData.nodes.length">
      <div class="topo-toolbar">
        <span class="label">字号</span>
        <el-slider
          v-model="labelFontSize"
          :min="6"
          :max="18"
          :step="1"
          class="font-slider"
        />
        <span class="label">显示标签</span>
        <el-switch v-model="showLabels" />
        <el-button size="small" class="fullscreen-btn" @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </el-button>
      </div>
      <a v-if="isFullscreen" class="back-home" href="#" @click.prevent="backHome">← 返回主页</a>
      <div ref="graphEl" class="graph" />
    </template>
    <div v-else class="empty">暂无设备</div>
  </div>
```

style 追加：

```css
.topology-wrap {
  position: relative;
}
.topology-wrap:fullscreen {
  height: 100vh;
  border-radius: 0;
}
.back-home {
  position: absolute;
  top: 12px;
  right: 16px;
  z-index: 10;
  color: #94a3b8;
  font-size: 13px;
  text-decoration: none;
  background: rgba(17, 28, 49, 0.85);
  border: 1px solid #1e293b;
  border-radius: 4px;
  padding: 4px 10px;
}
.back-home:hover {
  color: #e2e8f0;
}
.topo-toolbar .fullscreen-btn {
  margin-left: auto;
}
```

（`.topology-wrap` 原有属性保留，仅新增 position:relative 一条规则块。）

- [ ] **Step 4: Implement MainView 接线**

`MainView.vue:377`：

```html
        <el-tab-pane lazy label="拓扑图" name="topology">
          <el-card><TopologyView @back-home="activeTab = 'devices'" /></el-card>
        </el-tab-pane>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend; npx vitest run src/components/__tests__/TopologyView.spec.js src/views/__tests__/MainView.spec.js`
Expected: PASS（全部用例）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/TopologyView.vue frontend/src/views/MainView.vue frontend/src/components/__tests__/TopologyView.spec.js frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: in-page fullscreen mode with back-home link for topology"
```

---

### Task 6: 全量回归 + 构建 + 手动验证

**Files:**
- 无新改动（验证任务）

**Interfaces:**
- Consumes: Task 1-5 全部产出

- [ ] **Step 1: 全量前端测试**

Run: `cd frontend; npm test`
Expected: 全部通过（当前基线 120 条 + 新增约 9 条）

- [ ] **Step 2: 构建**

Run: `cd frontend; npm run build`
Expected: 成功无报错

- [ ] **Step 3: 手动浏览器验证**

启动本地服务（backend uvicorn :8000 + frontend vite），Playwright 或手动检查：

1. 拓扑页点「全屏」→ 页头/tab 消失、画布铺满、右上角「← 返回主页」可见
2. 点「← 返回主页」→ 回到设备页签
3. 悬停节点、等待 30s 轮询 → 图不重新布局；拖拽节点松手后位置保持
4. 节点为大圆点内含类型图标（交换机 🔀 等）；自定义类型显示首字
5. 字号滑块初始在最左侧（6）
6. 控制台无报错

- [ ] **Step 4: 版本发布（用户确认后执行）**

bump `backend/app/main.py` 与 `frontend/package.json` 至 0.5.0（UI 功能集合），
commit + tag + push，CI success 后由用户部署到 iStoreOS 验证。

```bash
git tag 0.5.0; git push origin main --tags
```
