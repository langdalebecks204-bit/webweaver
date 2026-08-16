# 设备类型收起 + ICMP ping 自定义实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将设备页工具栏中占一整行的设备类型管理改为默认收起的折叠面板，并为 ICMP 巡检新增可配置的 ping 次数（1-10）与包大小（32-10000 字节），全局设置、保存即生效。

**Architecture:** 两个独立功能，互不依赖。设备类型收起为纯前端改动（`MainView.vue` 用 `ref` + `el-collapse-transition` 内联折叠）。ICMP ping 自定义为前后端：新增 `ping_count`/`ping_packet_size` 两个 `Setting` 键（仿 `poll_interval_minutes` 持久化模式），`icmp_ping` 改为循环发送 `ping_count` 次（带 `size`），成功次数超过半数判在线、成功延时取平均；`run_inspection`/`run_external_inspection` 入口各读一次设置逐设备传入。

**Tech Stack:** Vue 3 `<script setup>`、Pinia、Element Plus、vitest + happy-dom、FastAPI、SQLAlchemy、pytest、ping3 4.0.2（`async_ping` 支持 `size` 参数）。

## Global Constraints

- ping 次数范围 1–10，默认 3；包大小范围 32–10000 字节，默认 56。
- 在线判定：成功次数 `> count // 2`（超过半数），count=1 时需 ≥1。
- 延时取成功次的平均值 `int(round(sum/len))`。
- 保存即生效：下次巡检（含"立即巡检全部"）即用新值，无需重启。
- 设置 API admin-only（viewer 403），范围越界 Pydantic 返回 422。
- 不改 `ping_timeout`/`ping_concurrency`（保持环境变量配置）。
- 设备类型收起默认收起，不持久化展开状态（刷新恢复收起）。
- 修改中文文件必须用 Edit/Read 工具，禁止 PowerShell `Set-Content -Encoding UTF8`（会加 BOM 并损坏中文）。

---

### Task 1: 后端设置服务 get/set ping 参数

**Files:**
- Modify: `backend/app/services/setting_service.py`
- Test: `backend/tests/test_settings_api.py`

**Interfaces:**
- Produces: `get_ping_params(db: Session) -> tuple[int, int]`、`set_ping_params(db: Session, count: int, size: int) -> tuple[int, int]`；键 `ping_count`、`ping_packet_size`（常量 `PING_COUNT_KEY`、`PING_PACKET_SIZE_KEY`）。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_settings_api.py` 追加：

```python
def test_ping_params_default(client, admin_headers):
    r = client.get("/api/settings/ping-params", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"ping_count": 3, "ping_packet_size": 56}


def test_ping_params_put_persists(client, admin_headers):
    r = client.put(
        "/api/settings/ping-params",
        headers=admin_headers,
        json={"ping_count": 5, "ping_packet_size": 128},
    )
    assert r.status_code == 200
    assert r.json() == {"ping_count": 5, "ping_packet_size": 128}

    got = client.get("/api/settings/ping-params", headers=admin_headers)
    assert got.json() == {"ping_count": 5, "ping_packet_size": 128}

    with SessionLocal() as db:
        assert db.get(Setting, "ping_count").value == "5"
        assert db.get(Setting, "ping_packet_size").value == "128"


def test_ping_params_admin_only(client, admin_headers):
    vh = _mk_viewer(client)
    assert client.get("/api/settings/ping-params", headers=vh).status_code == 403
    assert client.put(
        "/api/settings/ping-params", headers=vh, json={"ping_count": 3, "ping_packet_size": 56}
    ).status_code == 403


def test_ping_params_out_of_range(client, admin_headers):
    assert client.put(
        "/api/settings/ping-params", headers=admin_headers,
        json={"ping_count": 0, "ping_packet_size": 56},
    ).status_code == 422
    assert client.put(
        "/api/settings/ping-params", headers=admin_headers,
        json={"ping_count": 11, "ping_packet_size": 56},
    ).status_code == 422
    assert client.put(
        "/api/settings/ping-params", headers=admin_headers,
        json={"ping_count": 3, "ping_packet_size": 31},
    ).status_code == 422
    assert client.put(
        "/api/settings/ping-params", headers=admin_headers,
        json={"ping_count": 3, "ping_packet_size": 10001},
    ).status_code == 422
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_settings_api.py -k ping_params -q`（backend 目录）
Expected: FAIL（路由不存在 → 404/断言错误）。

- [ ] **Step 3: 实现设置服务函数**

在 `backend/app/services/setting_service.py` 的常量区追加：

```python
PING_COUNT_KEY = "ping_count"
PING_PACKET_SIZE_KEY = "ping_packet_size"
```

在文件末尾追加：

```python
def get_ping_params(db: Session) -> tuple[int, int]:
    count_row = db.get(Setting, PING_COUNT_KEY)
    size_row = db.get(Setting, PING_PACKET_SIZE_KEY)
    count = int(count_row.value) if count_row is not None else settings.ping_count
    size = int(size_row.value) if size_row is not None else settings.ping_packet_size
    return count, size


def set_ping_params(db: Session, count: int, size: int) -> tuple[int, int]:
    for key, value in ((PING_COUNT_KEY, count), (PING_PACKET_SIZE_KEY, size)):
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=str(value)))
        else:
            row.value = str(value)
    db.commit()
    return count, size
```

- [ ] **Step 4: 在 `config.py` 添加默认值**

在 `backend/app/config.py` 的 `ping_timeout` 后追加：

```python
    ping_count: int = 3
    ping_packet_size: int = 56
```

- [ ] **Step 5: 添加 API 路由**

在 `backend/app/routers/settings.py` 中：import 追加 `get_ping_params, set_ping_params`；新增：

```python
class PingParamsUpdate(BaseModel):
    ping_count: int = Field(ge=1, le=10)
    ping_packet_size: int = Field(ge=32, le=10000)


@router.get("/ping-params")
def get_ping_params_route(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    count, size = get_ping_params(db)
    return {"ping_count": count, "ping_packet_size": size}


@router.put("/ping-params")
def update_ping_params_route(
    payload: PingParamsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    count, size = set_ping_params(db, payload.ping_count, payload.ping_packet_size)
    return {"ping_count": count, "ping_packet_size": size}
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_settings_api.py -k ping_params -q`（backend 目录）
Expected: 4 passed。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/setting_service.py backend/app/config.py backend/app/routers/settings.py backend/tests/test_settings_api.py
git commit -m "feat: configurable ICMP ping count and packet size via settings API"
```

---

### Task 2: 后端引擎多次 ping

**Files:**
- Modify: `backend/app/inspector/engine.py`
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `get_ping_params(db)`（Task 1 产出）。
- Produces: `icmp_ping(host: str, timeout: float, count: int, packet_size: int) -> int | None`；`probe_device(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size)`；`run_inspection`/`run_external_inspection` 内部读取设置。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_engine.py` 顶部 import 追加 `icmp_ping`。追加测试：

```python
async def test_icmp_ping_multiple_majority_online(monkeypatch):
    results = [12, 16, None]
    calls = []

    async def fake_async_ping(host, timeout, size, unit):
        calls.append((host, timeout, size, unit))
        return results.pop(0)

    monkeypatch.setattr("app.inspector.engine.async_ping", fake_async_ping)
    assert await icmp_ping("10.0.0.1", 1.0, 3, 128) == 14
    assert calls == [("10.0.0.1", 1.0, 128, "ms"), ("10.0.0.1", 1.0, 128, "ms"), ("10.0.0.1", 1.0, 128, "ms")]


async def test_icmp_ping_offline_when_not_majority(monkeypatch):
    results = [12, None, None]

    async def fake_async_ping(host, timeout, size, unit):
        return results.pop(0)

    monkeypatch.setattr("app.inspector.engine.async_ping", fake_async_ping)
    assert await icmp_ping("10.0.0.1", 1.0, 3, 56) is None


async def test_icmp_ping_single_count(monkeypatch):
    async def fake_async_ping(host, timeout, size, unit):
        return 5

    monkeypatch.setattr("app.inspector.engine.async_ping", fake_async_ping)
    assert await icmp_ping("10.0.0.1", 1.0, 1, 56) == 5
```

同时把现有 3 个 `test_probe_*` 的 `probe_device(...)` 调用补上新参数 `, 3, 56`（如 `probe_device("10.0.0.1", 443, 1.0, 2.0, 3, 56)`），并保持 `icmp_ping` monkeypatch 签名不变。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_engine.py -q`（backend 目录）
Expected: 新测试 FAIL（`icmp_ping` 缺参数），现有 probe 测试因签名不符 FAIL。

- [ ] **Step 3: 实现多次 ping**

修改 `backend/app/inspector/engine.py`：

```python
async def icmp_ping(host: str, timeout: float, count: int, packet_size: int) -> int | None:
    latencies = []
    for _ in range(count):
        try:
            latency = await async_ping(host, timeout=timeout, size=packet_size, unit="ms")
        except Exception:
            latency = None
        if latency is not None and latency is not False:
            latencies.append(latency)
    if len(latencies) <= count // 2:
        return None
    return int(round(sum(latencies) / len(latencies)))
```

修改 `probe_device` 签名并传参：

```python
async def probe_device(
    ip: str, port: int | None, ping_timeout: float, tcp_timeout: float,
    ping_count: int, ping_packet_size: int,
) -> ProbeResult:
    latency = await icmp_ping(ip, ping_timeout, ping_count, ping_packet_size)
    ...
```

- [ ] **Step 4: 让 run_inspection / run_external_inspection 读取设置**

修改 `run_inspection`：在 `check_one` 闭包外读一次设置：

```python
    ping_count, ping_packet_size = get_ping_params(db)
```

`check_one` 内调用改为：

```python
            result = await probe_device(
                device.ip_address, device.port, settings.ping_timeout, settings.tcp_timeout,
                ping_count, ping_packet_size,
            )
```

修改 `run_external_inspection` 同样在 `check_one` 外读一次，两处 `probe_device` 调用补 `ping_count, ping_packet_size`。

在 import 追加：`from app.services.setting_service import get_ping_params, get_probe_history_days`（合并现有 import）。

- [ ] **Step 5: 更新现有测试适配新签名**

`backend/tests/test_engine.py` 中 `test_run_inspection_*` 与 `test_run_external_inspection_*` 的 `fake_probe` 签名改为 `async def fake_probe(ip, port, ping_timeout, tcp_timeout, ping_count, ping_packet_size)`。

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_engine.py -q`（backend 目录）
Expected: 全部通过（新增 3 + 原有 10）。

- [ ] **Step 7: 全量后端回归**

Run: `python -m pytest -q`（backend 目录）
Expected: 131 passed（原 124 + settings API 4 + engine 3）。

- [ ] **Step 8: 提交**

```bash
git add backend/app/inspector/engine.py backend/tests/test_engine.py
git commit -m "feat: ICMP ping multiple attempts with packet size and majority verdict"
```

---

### Task 3: 前端设置 store 与 API

**Files:**
- Modify: `frontend/src/api/settings.js`
- Modify: `frontend/src/stores/settings.js`
- Test: `frontend/src/stores/__tests__/settings.spec.js`

**Interfaces:**
- Consumes: 后端 `GET/PUT /api/settings/ping-params`（Task 1 产出）。
- Produces: `fetchPingParams()`、`updatePingParams(count, size)`；store state `pingCount: 3`、`pingPacketSize: 56`；actions `loadPingParams()`、`savePingParams(count, size)`。

- [ ] **Step 1: 写失败测试**

在 `frontend/src/stores/__tests__/settings.spec.js` 顶部 hoisted mock 追加 `fetchPingMock`、`updatePingMock` 并注册。追加 describe：

```js
describe('settings ping 参数', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadPingParams 拉取当前 ping 参数', async () => {
    fetchPingMock.mockResolvedValue({ data: { ping_count: 5, ping_packet_size: 128 } })
    const store = useSettingsStore()
    await store.loadPingParams()
    expect(store.pingCount).toBe(5)
    expect(store.pingPacketSize).toBe(128)
  })

  it('savePingParams 调用接口并更新 state', async () => {
    updatePingMock.mockResolvedValue({ data: { ping_count: 8, ping_packet_size: 256 } })
    const store = useSettingsStore()
    await store.savePingParams(8, 256)
    expect(updatePingMock).toHaveBeenCalledWith(8, 256)
    expect(store.pingCount).toBe(8)
    expect(store.pingPacketSize).toBe(256)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run src/stores/__tests__/settings.spec.js`（frontend 目录）
Expected: FAIL（`loadPingParams` 不是函数）。

- [ ] **Step 3: 实现 API 函数**

在 `frontend/src/api/settings.js` 末尾追加：

```js
export function fetchPingParams() {
  return client.get('/settings/ping-params')
}

export function updatePingParams(count, size) {
  return client.put('/settings/ping-params', { ping_count: count, ping_packet_size: size })
}
```

- [ ] **Step 4: 实现 store**

`frontend/src/stores/settings.js`：import 追加 `fetchPingParams, updatePingParams`；state 追加 `pingCount: 3, pingPacketSize: 56`；actions 追加：

```js
    async loadPingParams() {
      const { data } = await fetchPingParams()
      this.pingCount = data.ping_count
      this.pingPacketSize = data.ping_packet_size
    },
    async savePingParams(count, size) {
      const { data } = await updatePingParams(count, size)
      this.pingCount = data.ping_count
      this.pingPacketSize = data.ping_packet_size
    },
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npx vitest run src/stores/__tests__/settings.spec.js`（frontend 目录）
Expected: 全部通过（原 5 + 新 2）。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/settings.js frontend/src/stores/settings.js frontend/src/stores/__tests__/settings.spec.js
git commit -m "feat: settings store for ping count and packet size"
```

---

### Task 4: MainView 设备类型折叠 + ping 参数 UI

**Files:**
- Modify: `frontend/src/views/MainView.vue`
- Test: `frontend/src/views/__tests__/MainView.spec.js`

**Interfaces:**
- Consumes: store `settings.pingCount`/`pingPacketSize`/`savePingParams`/`loadPingParams`（Task 3 产出）。
- Produces: 设备页工具栏"设备类型"折叠按钮 + 内联面板；"ping次数"/"包大小"输入框 + "保存巡检参数"按钮；`typesExpanded` ref。

- [ ] **Step 1: 写失败测试**

在 `frontend/src/views/__tests__/MainView.spec.js` 的 hoisted mock 追加 `loadPingParamsMock`、`savePingParamsMock` 并注册到 settings store mock。追加 describe：

```js
describe('MainView ping 参数设置', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示次数/包大小并可保存', async () => {
    authState.role = 'admin'
    savePingParamsMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '保存巡检参数').trigger('click')
    await flushPromises()
    expect(savePingParamsMock).toHaveBeenCalledWith(3, 56)
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('viewer 不显示巡检参数设置', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('保存巡检参数')
  })
})

describe('MainView 设备类型收起', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('默认收起，点击展开后显示标签与添加控件', async () => {
    authState.role = 'admin'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('设备类型')
    const collapsedContent = wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))
    expect(collapsedContent).toBeFalsy()
    await buttonByText(wrapper, '设备类型').trigger('click')
    await flushPromises()
    const addInput = wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))
    expect(addInput).toBeTruthy()
  })

  it('展开后添加自定义类型', async () => {
    authState.role = 'admin'
    addTypeMock.mockResolvedValue()
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '设备类型').trigger('click')
    await flushPromises()
    const addInput = wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))
    await addInput.setValue('nas2')
    const addBtn = wrapper.findAll('button').find((b) => b.text() === '添加')
    await addBtn.trigger('click')
    await flushPromises()
    expect(addTypeMock).toHaveBeenCalledWith('nas2')
  })

  it('viewer 不显示设备类型按钮', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('设备类型')
  })
})
```

同时**修改现有测试** `MainView 设备类型管理` describe 中的"admin 显示类型管理，添加自定义类型"和"删除自定义类型需确认"测试：先 `await buttonByText(wrapper, '设备类型').trigger('click')` 展开再断言输入框/移除按钮。

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run src/views/__tests__/MainView.spec.js`（frontend 目录）
Expected: 新增测试 FAIL（无"保存巡检参数"按钮、无"设备类型"按钮）；修改后的旧测试 FAIL（展开前找不到输入框）。

- [ ] **Step 3: 实现 MainView script**

在 `MainView.vue` script 的 `newTypeName` 附近追加：

```js
const typesExpanded = ref(false)
```

`onMounted` 中 admin 分支追加 `await settings.loadPingParams()`：

```js
  if (auth.user?.role === 'admin') {
    await settings.loadInterval()
    await settings.loadPingParams()
  }
```

追加保存函数（放 `onSaveInterval` 后）：

```js
async function onSavePingParams() {
  try {
    await settings.savePingParams(settings.pingCount, settings.pingPacketSize)
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}
```

- [ ] **Step 4: 实现 MainView 模板**

将 `.interval-setting` 块后追加 ping 参数控件，并改造设备类型区为折叠。修改 `MainView.vue` 模板中工具栏部分：

```html
                <div v-if="isAdmin" class="interval-setting">
                  <el-input-number
                    v-model="settings.pollIntervalMinutes"
                    :min="1"
                    :max="1440"
                    size="small"
                  />
                  <el-button size="small" @click="onSaveInterval">保存间隔</el-button>
                </div>
                <div v-if="isAdmin" class="ping-setting">
                  <el-input-number
                    v-model="settings.pingCount"
                    :min="1"
                    :max="10"
                    size="small"
                  />
                  <el-input-number
                    v-model="settings.pingPacketSize"
                    :min="32"
                    :max="10000"
                    size="small"
                  />
                  <el-button size="small" @click="onSavePingParams">保存巡检参数</el-button>
                </div>
                <div class="stats">
                  <el-tag type="success">在线 {{ store.stats.online }}</el-tag>
                  <el-tag type="warning">警告 {{ store.stats.warning }}</el-tag>
                  <el-tag type="danger">离线 {{ store.stats.offline }}</el-tag>
                  <el-tag type="info">未知 {{ store.stats.unknown }}</el-tag>
                </div>
                <div v-if="isAdmin" class="type-manage">
                  <el-button size="small" @click="typesExpanded = !typesExpanded">
                    设备类型{{ typesExpanded ? ' ▴' : ' ▾' }}
                  </el-button>
                  <el-collapse-transition>
                    <div v-if="typesExpanded" class="type-content">
                      <span>设备类型：</span>
                      <el-tag
                        v-for="t in settings.builtinTypes"
                        :key="t"
                        size="small"
                        class="type-tag"
                      >
                        {{ typeLabel(t) }}（内置）
                      </el-tag>
                      <el-tag
                        v-for="t in settings.customTypes"
                        :key="t"
                        size="small"
                        closable
                        @close="onRemoveCustomType(t)"
                        class="type-tag"
                      >
                        {{ t }}
                      </el-tag>
                      <el-input
                        v-model="newTypeName"
                        placeholder="自定义类型名"
                        size="small"
                        class="type-input"
                      />
                      <el-button size="small" type="primary" @click="onAddCustomType">添加</el-button>
                    </div>
                  </el-collapse-transition>
                </div>
```

- [ ] **Step 5: 实现 MainView 样式**

在 `<style scoped>` 追加：

```css
.ping-setting {
  display: flex;
  align-items: center;
  gap: 8px;
}
.type-content {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  width: 100%;
}
```

同时将 `.toolbar` 样式改为 `flex-wrap: wrap;` 以允许类型面板换行：

```css
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
```

- [ ] **Step 6: 运行测试确认通过**

Run: `npx vitest run src/views/__tests__/MainView.spec.js`（frontend 目录）
Expected: 全部通过。

- [ ] **Step 7: 全量前端回归 + 构建**

Run: `npm test`（frontend 目录），再 `npm run build`
Expected: 前端 110+ 测试全过，build 成功。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/views/MainView.vue frontend/src/views/__tests__/MainView.spec.js
git commit -m "feat: collapse device type panel and add ping param controls in toolbar"
```

---

### Task 5: 真实浏览器验证 + 版本发布

**Files:**
- Modify: `backend/app/main.py`、`frontend/package.json`（版本号 0.4.6 → 0.4.7）

**Interfaces:**
- Consumes: Task 1-4 全部产物。

- [ ] **Step 1: 启动 preview 并用 playwright 验证**

启动 preview：`npx vite preview --port 4173 --strictPort`（后台）。
用 playwright-core（`frontend/node_modules`）+ 系统 Edge 打开 `http://localhost:4173/`，登录 admin/admin123（路由 `/api/**` 转发到 `http://10.0.11.252:8000`），进入设备页验证：
- 默认"设备类型"按钮可见、标签内容不可见；点击后标签与添加输入框出现。
- "保存巡检参数"按钮可见，次数/包大小输入框存在。

预期：无 console error。

- [ ] **Step 2: 后端行为验证（可选用 pytest 已覆盖）**

无需真实 ping（CI 环境无外网 ICMP），由 Task 2 单测覆盖多数/单次判定。

- [ ] **Step 3: 版本 bump 并发布**

用 Edit 工具将 `backend/app/main.py` 与 `frontend/package.json` 中版本 `0.4.6` 改为 `0.4.7`。

```bash
git add backend/app/main.py frontend/package.json
git commit -m "chore: bump version to 0.4.7"
git tag 0.4.7
git push origin main --tags
```

- [ ] **Step 4: CI 轮询**

REST API 查询 Actions runs（sha 匹配），轮询直到 `status=completed`、`conclusion=success`。

- [ ] **Step 5: ghcr 确认**

`https://ghcr.io/token?scope=repository:langdalebecks204-bit/webweaver:pull` 取 token，`GET /v2/langdalebecks204-bit/webweaver/manifests/0.4.7` 返回 200 与 digest。

- [ ] **Step 6: 清理**

停 preview 进程，删除临时 playwright 脚本。

```bash
git push origin --tags  # 已含 tags；如需单独推 tag
```