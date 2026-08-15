# 拓扑图节点标签控制实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在拓扑图页顶部添加工具栏，支持节点标签字号调整（6–18px，默认 9px，实时生效）与标签显示/隐藏（隐藏时悬停节点临时显示）。

**Architecture:** 全部改动在 `TopologyView.vue`。新增响应式 `labelFontSize`/`showLabels` 状态；`drawNode` 绘制时读取这两个状态决定字号与是否绘制标签文字。工具栏为 `.topology-wrap` 内的横向 flex 条，`.topology-wrap` 改为纵向 flex 让 `.graph` 占剩余空间。force-graph 动画循环每帧重绘，滑块改 `ref` 即实时生效，无需重建图。

**Tech Stack:** Vue 3 `<script setup>`、Element Plus（`el-slider`、`el-switch`）、vitest + happy-dom + @vue/test-utils。

## Global Constraints

- 字号范围固定 6–18，步进 1，默认 9。
- 默认显示标签（`showLabels = true`）。
- 隐藏标签时，悬停节点（`hoverNodeId`）仍显示标签。
- 不新增后端改动、不做设置持久化（刷新后恢复默认）。
- 测试文件为 `frontend/src/components/__tests__/TopologyView.spec.js`，使用已有 force-graph mock（`createMock`）与 `treeMock`。
- 修改中文文件必须用 Edit/Read 工具，禁止 PowerShell `Set-Content -Encoding UTF8`（会加 BOM 并损坏中文）。

---

### Task 1: 字号与显示状态 + 绘制逻辑

**Files:**
- Modify: `frontend/src/components/TopologyView.vue:9-10,58-79`
- Test: `frontend/src/components/__tests__/TopologyView.spec.js`

**Interfaces:**
- Produces: `labelFontSize`（`ref<number>`，默认 9）、`showLabels`（`ref<boolean>`，默认 true）；`drawNode(node, ctx)` 内部逻辑变更。

- [ ] **Step 1: 添加失败测试**

在 `TopologyView.spec.js` 的 `describe` 内追加两个测试（放在 `数据异步加载完成后创建图谱` 之后）：

```js
it('标签字号可调整且影响绘制', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  const draw = fgMock.nodeCanvasObject.mock.calls[0][0]
  const ctx = { fillStyle: '', font: '', textAlign: '', fillText: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(), globalAlpha: 1, shadowColor: '', shadowBlur: 0 }
  const node = { id: 3, name: '节点C', status: 'online', val: 8, x: 10, y: 10 }
  draw(node, ctx)
  expect(ctx.font).toBe('9px sans-serif')
  // 修改字号
  const slider = wrapper.findComponent({ name: 'ElSlider' })
  expect(slider.exists()).toBe(true)
  wrapper.vm.labelFontSize = 14
  await flushPromises()
  draw(node, ctx)
  expect(ctx.font).toBe('14px sans-serif')
})

it('隐藏标签时非悬停节点不显示文字，悬停节点仍显示', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  const draw = fgMock.nodeCanvasObject.mock.calls[0][0]
  const ctx = { fillStyle: '', font: '', textAlign: '', fillText: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(), globalAlpha: 1, shadowColor: '', shadowBlur: 0 }
  const node = { id: 3, name: '节点C', status: 'online', val: 8, x: 10, y: 10 }
  wrapper.vm.showLabels = false
  await flushPromises()
  draw(node, ctx)
  expect(ctx.fillText).not.toHaveBeenCalled()
  // 模拟悬停
  fgMock.onNodeHover.mock.calls[0][0](node)
  draw(node, ctx)
  expect(ctx.fillText).toHaveBeenCalledWith('节点C', 10, expect.any(Number))
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: 新增两测试失败——`ctx.font` 为 `12px sans-serif`（非 `9px`）、`showLabels` 相关断言失败（属性不存在）、`ElSlider` 不存在。

- [ ] **Step 3: 实现状态与绘制逻辑**

修改 `TopologyView.vue`：

第 9-10 行后添加：

```js
const labelFontSize = ref(9)
const showLabels = ref(true)
```

修改 `drawNode`（第 58-79 行）末尾文字绘制部分：

```js
  ctx.globalAlpha = 1
  if (showLabels.value || node.id === hoverNodeId.value) {
    ctx.fillStyle = 'rgba(255,255,255,0.85)'
    ctx.font = `${labelFontSize.value}px sans-serif`
    ctx.textAlign = 'center'
    ctx.fillText(node.name, node.x, node.y - r - 4)
  }
```

同时移除原有硬编码两行：

```js
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.font = '12px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(node.name, node.x, node.y - r - 4)
```

（`ctx.globalAlpha = 1` 保留在 `if` 前。）

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: 全绿（含既有 4 个测试）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/TopologyView.vue frontend/src/components/__tests__/TopologyView.spec.js
git commit -m "feat: make topology node label font size adjustable and hideable"
```

---

### Task 2: 工具栏 UI

**Files:**
- Modify: `frontend/src/components/TopologyView.vue:138-166`

**Interfaces:**
- Consumes: `labelFontSize`、`showLabels`（Task 1 产物）。
- Produces: 模板中工具栏（滑块绑定 `labelFontSize`，开关绑定 `showLabels`）；样式调整 `.topology-wrap`/`.graph`。

- [ ] **Step 1: 添加失败测试**

在 `TopologyView.spec.js` 追加：

```js
it('拓扑图页渲染字号滑块与显示标签开关', async () => {
  wrapper = mount(TopologyView, {
    global: { stubs: { ElSlider: true, ElSwitch: true } },
  })
  await flushPromises()
  expect(wrapper.find('.topo-toolbar').exists()).toBe(true)
  expect(wrapper.findComponent({ name: 'ElSlider' }).exists()).toBe(true)
  expect(wrapper.findComponent({ name: 'ElSwitch' }).exists()).toBe(true)
  expect(wrapper.text()).toContain('字号')
  expect(wrapper.text()).toContain('显示标签')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: `.topo-toolbar` 不存在 → 失败。

- [ ] **Step 3: 实现工具栏模板与样式**

修改模板（第 138-144 行）：

```html
<template>
  <div class="topology-wrap">
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
      </div>
      <div ref="graphEl" class="graph" />
    </template>
    <div v-else class="empty">暂无设备</div>
  </div>
</template>
```

修改样式（第 146-166 行）：

```css
.topology-wrap {
  width: 100%;
  height: calc(100vh - 200px);
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.topo-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  color: #94a3b8;
  background: #111c31;
  border-bottom: 1px solid #1e293b;
}
.topo-toolbar .label {
  font-size: 13px;
  white-space: nowrap;
}
.topo-toolbar .font-slider {
  width: 160px;
  margin: 0 8px;
}
.graph {
  flex: 1;
  width: 100%;
  min-height: 0;
}
.error {
  color: #ef4444;
  padding: 24px;
}
.empty {
  color: #94a3b8;
  padding: 24px;
}
```

注意：`el-slider`/`el-switch` 是 Element Plus 全局组件，`MainView.vue` 已全局注册，无需额外 import。

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run src/components/__tests__/TopologyView.spec.js`
Expected: 全绿。

- [ ] **Step 5: 全量回归**

Run: `npm test`
Expected: 前端 18 文件 / 全测试通过。

Run: `python -m pytest -q`（`backend` 目录）
Expected: 124 passed（不受影响，用于确认）。

- [ ] **Step 6: 构建验证**

Run: `npm run build`（`frontend` 目录）
Expected: build 成功，无 error。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/TopologyView.vue frontend/src/components/__tests__/TopologyView.spec.js
git commit -m "feat: add topology graph toolbar with font size and label toggle"
```