# 前端自动刷新 + 节点移动 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让前端每 30 秒自动刷新设备树（状态随调度器自动更新），并在设备编辑弹窗中加入「上级分组」下拉选择器以支持把节点移动到不同上下级。

**Architecture:** 全部改动在 `frontend/`。自动刷新：`MainView.vue` 挂载时启动 `setInterval(() => store.load(), 30000)`，卸载时 `clearInterval`。节点移动：`DeviceTree.vue` 编辑弹窗加 `el-select` 父级选择器，候选来自 `store.tree` 展平并排除自身及后代，保存时把选中的 `parent_id` 提交（后端 `update_device` 已支持改 parent_id 并有环检测）。

**Tech Stack:** Vue 3 + Pinia + Element Plus + Vitest（前端）。

## Global Constraints

- 前端测试命令（workdir=frontend）：`npm run test`；构建：`npm run build`。
- 前端测试用 Vitest + `@vue/test-utils` + `happy-dom`（已在 package.json devDependencies）。组件测试文件首行需 `// @vitest-environment happy-dom`。
- 刷新间隔固定 **30 秒**；刷新须静默（不阻塞用户操作、不打断右键菜单/弹窗）。
- 父级候选必须排除自身及其所有后代（防环）；清空选择表示移到根级（`parent_id = null`）。
- 后端已有防线：`parent cannot be self`、`cycle not allowed`、同父重名 `device name already exists under this parent`（→409）。前端过滤为第一道防护。
- 保存失败沿用现有 `ElMessage.error(error.response?.data?.detail || '保存失败')`，弹窗保持打开。
- 无代码注释（除非必需）。
- 提交信息以 `feat:` 或 `test:` 或 `docs:` 前缀开头。
- 分支 `feature/phase1-minimal-loop`，worktree `D:\code\WebWeaver\.worktrees\phase1-minimal-loop`。

---

### Task 1: MainView 前端自动刷新（30 秒轮询）

**Files:**
- Modify: `frontend/src/views/MainView.vue:1-37`
- Test: `frontend/src/views/__tests__/MainView.spec.js`

**Interfaces:**
- Consumes: `useDevicesStore()` 的 `load()` action（返回 Promise，GET `/api/devices/tree`）。
- Produces: 无（纯 UI 行为）。

- [ ] **Step 1: 写失败测试**

向 `frontend/src/views/__tests__/MainView.spec.js` 追加以下 describe（文件末尾）。当前文件已有 MainView 挂载测试与 2 个新增根分组用例，保留不动；只追加。

```js
describe('MainView 自动刷新', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('挂载后每 30 秒自动调用 store.load()，卸载后停止', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(3)

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(90000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(3)
  })
})
```

注意：`mountView()`、`loadMock` 等均已在文件顶部定义（`vi.hoisted`）。`mountView()` 已在现有文件定义过；若你按顺序执行，直接用即可。

- [ ] **Step 2: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: FAIL — `loadMock` 首次调用计数为 1，但 `advanceTimersByTimeAsync(30000)` 后计数仍为 1（没有定时器）。

- [ ] **Step 3: 实现最小代码**

修改 `frontend/src/views/MainView.vue` 的 `<script setup>`：

```js
import { onMounted, onUnmounted } from 'vue'
```

并把 `onMounted` 改为：

```js
let refreshTimer

onMounted(async () => {
  await auth.loadMe()
  await store.load()
  refreshTimer = setInterval(() => store.load(), 30000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
```

模板部分不改。

- [ ] **Step 4: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/views/__tests__/MainView.spec.js`
Expected: PASS（4 个用例：2 个新增根分组 + 1 个自动刷新）。再跑全量 `npm run test`，Expected: 6 passed（含 DeviceTree 的 1 个）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/MainView.vue frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: auto-refresh device tree every 30s in MainView"
```

---

### Task 2: DeviceTree 编辑弹窗加父级选择器（节点移动）

**Files:**
- Modify: `frontend/src/components/DeviceTree.vue`
- Test: `frontend/src/components/__tests__/DeviceTree.spec.js`

**Interfaces:**
- Consumes: `useDevicesStore()` 的 `tree` state（树结构，节点含 `id/parent_id/name/type/ip_address/port/status/latency_ms/last_check/children`）、`update(id, payload)` action、`create(payload)` action。`props.node` 为当前节点（含 `children`）。
- Produces: 编辑弹窗含「上级分组」下拉，保存载荷的 `parent_id` 可为 `null`（根级）或父节点数字 id。组件新增计算属性 `parentCandidates`（排除自身及后代的节点列表，形如 `[{ id, name, depth }]`）。

- [ ] **Step 1: 先给测试文件加基础设施**

当前 `frontend/src/components/__tests__/DeviceTree.spec.js` 的 store mock 没有 `tree`，且 dropdown stub 固定发 `add-child`。需要：让 `tree` 可配置、dropdown 命令与节点可配置。整体替换第 1-88 行（import 到 `mountTree` 定义结束）：

```js
// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { createMock, updateMock, removeMock, recheckMock, successMock, errorMock, confirmMock, treeMock } =
  vi.hoisted(() => ({
    createMock: vi.fn(),
    updateMock: vi.fn(),
    removeMock: vi.fn(),
    recheckMock: vi.fn(),
    successMock: vi.fn(),
    errorMock: vi.fn(),
    confirmMock: vi.fn(),
    treeMock: [
      {
        id: 1,
        name: 'root',
        parent_id: null,
        type: 'group',
        status: 'unknown',
        children: [
          { id: 2, name: 'child', parent_id: 1, type: 'server', status: 'unknown', children: [] },
          {
            id: 3,
            name: 'sibling',
            parent_id: 1,
            type: 'server',
            status: 'unknown',
            children: [
              { id: 4, name: 'sub', parent_id: 3, type: 'server', status: 'unknown', children: [] },
            ],
          },
        ],
      },
    ],
  }))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { confirm: confirmMock, prompt: vi.fn() },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    tree: treeMock,
    create: createMock,
    update: updateMock,
    remove: removeMock,
    recheck: recheckMock,
  }),
}))

import DeviceTree from '../DeviceTree.vue'

const defaultNode = {
  id: 3,
  name: 'sibling',
  parent_id: 1,
  type: 'server',
  ip_address: '10.0.0.3',
  status: 'unknown',
  children: [
    { id: 4, name: 'sub', parent_id: 3, type: 'server', status: 'unknown', children: [] },
  ],
}

function mountTree(command = 'add-child', node = defaultNode) {
  return mount(DeviceTree, {
    props: { node },
    global: {
      stubs: {
        'el-dropdown': {
          emits: ['command'],
          template: `<div class="dd" @click="$emit('command', '${command}')"><slot /></div>`,
        },
        'el-dropdown-menu': { template: '<div><slot /></div>' },
        'el-dropdown-item': { template: '<span><slot /></span>' },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-select': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
        },
        'el-option': {
          props: ['value'],
          template: '<option :value="value"><slot /></option>',
        },
        'el-input-number': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
        },
        'el-icon': { template: '<span><slot /></span>' },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        Folder: { template: '<span />' },
        Connection: { template: '<span />' },
        Monitor: { template: '<span />' },
      },
    },
  })
}
```

注意：
- `el-dropdown` stub 用**模板字符串插值**注入命令（`'${command}'`），不要用 `vi.hoisted` 变量引用——运行时模板作用域取不到模块变量。
- 原文件中的 `describe('DeviceTree 提交', ...)`（创建失败用例）保留在 `mountTree` 定义之后，但把该用例内的 `mountTree()` 改为 `mountTree('add-child')`。该用例的 `props.node` 默认是 `defaultNode`（id=3），点 `.dd` 发 `add-child` → `openCreate(3)`，逻辑不变。
- `treeMock` 是 store 的 `tree`（含节点 1/2/3/4）；`defaultNode` 是当前编辑节点（id=3，有后代 id=4）。

- [ ] **Step 2: 写失败测试**

在 `describe('DeviceTree 提交', ...)` 之后追加：

```js
describe('DeviceTree 父级选择', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('编辑时父级选择器排除自身及其后代', async () => {
    const wrapper = mountTree('edit')
    await wrapper.find('.dd').trigger('click')
    const options = wrapper.findAll('.dlg select').at(1).findAll('option')
    const ids = options.map((o) => Number(o.attributes('value')))
    expect(ids).toEqual([1, 2])
  })

  it('保存时提交所选父级 id', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountTree('edit')
    await wrapper.find('.dd').trigger('click')
    await wrapper.findAll('.dlg select').at(1).setValue('2')
    await wrapper.findAll('.dlg button').find((b) => b.text() === '保存').trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(3, expect.objectContaining({ parent_id: 2 }))
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('清空父级选择表示移到根级', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountTree('edit')
    await wrapper.find('.dd').trigger('click')
    await wrapper.findAll('.dlg select').at(1).setValue('')
    await wrapper.findAll('.dlg button').find((b) => b.text() === '保存').trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(3, expect.objectContaining({ parent_id: null }))
  })
})
```

说明：编辑节点是 id=3（自身 + 后代 4 被排除），所以候选只剩 id=1、2，断言 `[1, 2]`。`.dlg select` 有两个（类型 + 上级分组），`.at(1)` 取第二个即上级分组。

- [ ] **Step 3: 运行测试验证失败**

Run（workdir=`frontend`）: `npm run test src/components/__tests__/DeviceTree.spec.js`
Expected: FAIL — `wrapper.findAll('.dlg select').at(1)` 不存在（`.at(1)` 抛错），因为编辑弹窗还没有父级选择器。

- [ ] **Step 4: 实现最小代码**

修改 `frontend/src/components/DeviceTree.vue`：

在 `<script setup>` 中 `import { ref }` 改为 `import { computed, ref } from 'vue'`，并在 `onCommand` 之后、`</script>` 之前新增：

```js
function collectDescendantIds(node, acc) {
  if (!node.children) return acc
  for (const c of node.children) {
    acc.add(c.id)
    collectDescendantIds(c, acc)
  }
  return acc
}

const excludeIds = computed(() => {
  const acc = new Set([props.node.id])
  return collectDescendantIds(props.node, acc)
})

const parentCandidates = computed(() => {
  const result = []
  const walk = (nodes, depth) => {
    for (const n of nodes) {
      if (excludeIds.value.has(n.id)) continue
      result.push({ id: n.id, name: n.name, depth })
      if (n.children && n.children.length) walk(n.children, depth + 1)
    }
  }
  walk(store.tree, 0)
  return result
})
```

`submit()` 中，把 payload 构建改为显式归一化 `parent_id`：

```js
async function submit() {
  const rawParentId = form.value.parent_id
  const parentId =
    rawParentId === '' || rawParentId === null || rawParentId === undefined
      ? null
      : Number(rawParentId)
  const payload = {
    ...form.value,
    parent_id: parentId,
    ip_address: form.value.ip_address || null,
    port: form.value.port || null,
  }
  try {
    if (editing.value) {
      await store.update(editing.value.id, payload)
    } else {
      await store.create(payload)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}
```

在模板 `el-form` 中、「类型」form-item 之后、「IP 地址」之前新增：

```html
<el-form-item label="上级分组">
  <el-select v-model="form.parent_id" clearable placeholder="根级" style="width: 100%">
    <el-option
      v-for="c in parentCandidates"
      :key="c.id"
      :value="c.id"
    >
      {{ '　'.repeat(c.depth) + c.name }}
    </el-option>
  </el-select>
</el-form-item>
```

注意：`openCreate`/`openEdit` 中 `form.value` 需保留 `parent_id` 键（现有代码已含）。`openCreate(parentId)` 的 `parent_id: parentId` 保持。

- [ ] **Step 5: 运行测试验证通过**

Run（workdir=`frontend`）: `npm run test src/components/__tests__/DeviceTree.spec.js`
Expected: PASS（4 个用例：原有 1 个 + 新增 3 个）。

- [ ] **Step 6: 全量回归 + 构建**

Run（workdir=`frontend`）: `npm run test`
Expected: 8 passed（MainView 4 + DeviceTree 4 + devicesHelpers 2 中的重复说明——实际为：devicesHelpers 2、MainView 3、DeviceTree 4 = 9；以实际输出为准，全部 passed）。

Run（workdir=`frontend`）: `npm run build`
Expected: `✓ built in ...`，仅有既存 chunk 大小警告。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/DeviceTree.vue frontend/src/components/__tests__/DeviceTree.spec.js
git commit -m "feat: add parent selector to device edit dialog for moving nodes"
```
