// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  createMock,
  loadMock,
  recheckAllMock,
  loadMeMock,
  logoutMock,
  pushMock,
  promptMock,
  successMock,
  errorMock,
  loadIntervalMock,
  saveIntervalMock,
  confirmMock,
  extLoadMock,
  extCreateMock,
  extUpdateMock,
  extRemoveMock,
  extCheckAllMock,
} = vi.hoisted(() => ({
  createMock: vi.fn(),
  loadMock: vi.fn(),
  recheckAllMock: vi.fn(),
  loadMeMock: vi.fn(),
  logoutMock: vi.fn(),
  pushMock: vi.fn(),
  promptMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  loadIntervalMock: vi.fn(),
  saveIntervalMock: vi.fn(),
  confirmMock: vi.fn(),
  extLoadMock: vi.fn(),
  extCreateMock: vi.fn(),
  extUpdateMock: vi.fn(),
  extRemoveMock: vi.fn(),
  extCheckAllMock: vi.fn(),
}))

const authState = vi.hoisted(() => ({ role: 'admin' }))

const extTargets = vi.hoisted(() => [
  { id: 1, name: '百度', ip_address: '8.8.8.8', domain: 'baidu.com', ip_status: 'online', ip_latency_ms: 10, domain_status: 'offline', domain_latency_ms: null },
])

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { prompt: promptMock, confirm: confirmMock },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    tree: [],
    stats: { online: 0, offline: 0, warning: 0, unknown: 0 },
    load: loadMock,
    create: createMock,
    recheckAll: recheckAllMock,
  }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({
    user: { username: 'admin', role: authState.role },
    loadMe: loadMeMock,
    logout: logoutMock,
  }),
}))

vi.mock('../../stores/settings', () => ({
  useSettingsStore: () => ({
    pollIntervalMinutes: 5,
    loadInterval: loadIntervalMock,
    saveInterval: saveIntervalMock,
  }),
}))

vi.mock('../../stores/external', () => ({
  useExternalStore: () => ({
    targets: extTargets,
    load: extLoadMock,
    create: extCreateMock,
    update: extUpdateMock,
    remove: extRemoveMock,
    checkAll: extCheckAllMock,
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  createRouter: () => ({ beforeEach: vi.fn() }),
  createWebHistory: () => ({}),
}))

import MainView from '../MainView.vue'

function mountView() {
  return mount(MainView, {
    global: {
      stubs: {
        DeviceTree: { template: '<div class="device-tree-stub" />' },
        DeviceTable: { template: '<div class="device-table-stub" />' },
        DeviceDetail: { template: '<div class="device-detail-stub" />' },
        UsersPanel: { template: '<div class="users-panel-stub" />' },
        BackupPanel: { template: '<div class="backup-panel-stub" />' },
        'el-radio-group': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<div class="view-switch"><slot /></div>',
        },
        'el-radio-button': {
          props: ['value'],
          emits: ['click'],
          template: '<button class="mode-btn" @click="$emit(\'click\')">{{ $attrs.label }}</button>',
        },
        'el-container': { template: '<div><slot /></div>' },
        'el-header': { template: '<header><slot /></header>' },
        'el-main': { template: '<main><slot /></main>' },
        'el-card': { template: '<div><slot name="header" /><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-tree': { template: '<div><slot /></div>' },
        'el-tabs': { template: '<div class="tabs"><slot /></div>' },
        'el-tab-pane': { template: '<div :data-label="$attrs.label"><slot /></div>' },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input class="t-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-input-number': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input class="interval-input" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
        },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

function buttonByText(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

describe('MainView 新增根分组', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    promptMock.mockResolvedValue({ value: '研发部' })
  })

  it('点击后弹窗询问分组名，并以输入名称创建', async () => {
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '新增根分组').trigger('click')
    expect(promptMock).toHaveBeenCalled()
    await flushPromises()
    expect(createMock).toHaveBeenCalledWith({ name: '研发部', type: 'group' })
  })

  it('创建失败（如同名被拒）时提示后端错误，不静默失败', async () => {
    createMock.mockRejectedValue({ response: { data: { detail: '已存在同名节点' } } })
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '新增根分组').trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('已存在同名节点')
  })
})

describe('MainView 自动刷新', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('挂载后每 30 秒自动刷新设备树，卸载后停止', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(1)
    expect(extLoadMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(2)
    expect(extLoadMock).toHaveBeenCalledTimes(2)

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(90000)
    await flushPromises()
    expect(loadMock).toHaveBeenCalledTimes(2)
  })
})

describe('MainView 立即巡检全部', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('点击按钮同时触发设备与外网检测', async () => {
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '立即巡检全部').trigger('click')
    await flushPromises()
    expect(recheckAllMock).toHaveBeenCalledTimes(1)
    expect(extCheckAllMock).toHaveBeenCalledTimes(1)
  })
})

describe('MainView 巡检间隔设置', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示保存间隔并可保存', async () => {
    authState.role = 'admin'
    saveIntervalMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '保存间隔').trigger('click')
    await flushPromises()
    expect(saveIntervalMock).toHaveBeenCalledWith(5)
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('viewer 不显示间隔设置', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('保存间隔')
  })
})

describe('MainView 外网页签', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染外网目标表格', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('百度')
    expect(wrapper.text()).toContain('8.8.8.8')
    expect(wrapper.text()).toContain('baidu.com')
  })

  it('立即检测按钮触发 external.checkAll', async () => {
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '立即检测').trigger('click')
    await flushPromises()
    expect(extCheckAllMock).toHaveBeenCalledTimes(1)
  })

  it('admin 新增外网目标并保存', async () => {
    authState.role = 'admin'
    extCreateMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '新增外网目标').trigger('click')
    await wrapper.findAll('.dlg input.t-input').at(0).setValue('新目标')
    await buttonByText(wrapper, '保存').trigger('click')
    await flushPromises()
    expect(extCreateMock).toHaveBeenCalledWith({
      name: '新目标',
      ip_address: null,
      domain: null,
      port: null,
    })
    expect(successMock).toHaveBeenCalledWith('已保存')
  })

  it('admin 删除外网目标需确认', async () => {
    authState.role = 'admin'
    confirmMock.mockResolvedValue()
    extRemoveMock.mockResolvedValue()
    const wrapper = mountView()
    await flushPromises()
    await buttonByText(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(extRemoveMock).toHaveBeenCalledWith(1)
    expect(successMock).toHaveBeenCalledWith('已删除')
  })

  it('viewer 不显示新增与删除按钮', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('新增外网目标')
    expect(wrapper.text()).not.toContain('删除')
  })
})

describe('MainView 管理页签', () => {  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示用户管理与备份与恢复页签', async () => {
    authState.role = 'admin'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-label="用户管理"]').exists()).toBe(true)
    expect(wrapper.find('[data-label="备份与恢复"]').exists()).toBe(true)
  })

  it('viewer 不显示管理页签', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-label="用户管理"]').exists()).toBe(false)
    expect(wrapper.find('[data-label="备份与恢复"]').exists()).toBe(false)
  })
})

describe('MainView 树形/表格切换', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('默认树形视图，切换后显示表格', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.device-tree-stub').exists()).toBe(true)
    expect(wrapper.find('.device-table-stub').exists()).toBe(false)
    const switchEl = wrapper.findComponent('.view-switch')
    switchEl.vm.$emit('update:modelValue', 'table')
    await flushPromises()
    expect(wrapper.find('.device-tree-stub').exists()).toBe(false)
    expect(wrapper.find('.device-table-stub').exists()).toBe(true)
  })
})
