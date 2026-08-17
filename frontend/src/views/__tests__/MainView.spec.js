// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  createMock,
  loadMock,
  recheckAllMock,
  updateMock,
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
  addTypeMock,
  removeTypeMock,
  loadTypesMock,
  loadPingParamsMock,
  savePingParamsMock,
} = vi.hoisted(() => ({
  createMock: vi.fn(),
  loadMock: vi.fn(),
  recheckAllMock: vi.fn(),
  updateMock: vi.fn(),
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
  addTypeMock: vi.fn(),
  removeTypeMock: vi.fn(),
  loadTypesMock: vi.fn(),
  loadPingParamsMock: vi.fn(),
  savePingParamsMock: vi.fn(),
}))

const authState = vi.hoisted(() => ({ role: 'admin' }))

const devTree = vi.hoisted(() => [
  {
    id: 1,
    name: '机房A',
    parent_id: null,
    type: 'group',
    location: null,
    status: 'unknown',
    children: [
      {
        id: 2,
        name: '核心交换机',
        type: 'switch',
        parent_id: 1,
        ip_address: '10.0.0.1',
        port: 22,
        location: '机架1',
        status: 'online',
        children: [],
      },
    ],
  },
])

const extTargets = vi.hoisted(() => [
  { id: 1, name: '百度', ip_address: '8.8.8.8', domain: 'baidu.com', ip_status: 'online', ip_latency_ms: 10, domain_status: 'offline', domain_latency_ms: null },
])

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { prompt: promptMock, confirm: confirmMock },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    tree: devTree,
    stats: { online: 0, offline: 0, warning: 0, unknown: 0 },
    load: loadMock,
    create: createMock,
    update: updateMock,
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
    pingCount: 3,
    pingPacketSize: 56,
    loadPingParams: loadPingParamsMock,
    savePingParams: savePingParamsMock,
    builtinTypes: ['group', 'server', 'switch', 'terminal', 'camera', 'nvr', 'router', 'firewall', 'ap', 'printer', 'nas', 'ups'],
    customTypes: ['nas2'],
    typesLoaded: true,
    loadTypes: loadTypesMock,
    addType: addTypeMock,
    removeType: removeTypeMock,
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

describe('MainView 交换机端口字段', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('交换机类显示端口字段与配置按钮', async () => {
    authState.role = 'admin'
    updateMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    wrapper.vm.viewMode = 'table'
    await wrapper.vm.$nextTick()
    await wrapper.find('.table-edit').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('端口总数')
    expect(wrapper.text()).toContain('上联端口')
    expect(wrapper.text()).toContain('配置端口绑定')
  })

  it('非交换机类不显示端口字段', async () => {
    authState.role = 'admin'
    const wrapper = mountView()
    await flushPromises()
    wrapper.vm.viewMode = 'table'
    await wrapper.vm.$nextTick()
    await wrapper.find('.table-edit').trigger('click')
    await flushPromises()
    wrapper.vm.deviceForm.type = 'group'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('端口总数')
    expect(wrapper.text()).not.toContain('配置端口绑定')
  })
})

describe('MainView 拓扑图页签', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('包含拓扑图页签', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-label="拓扑图"]').exists()).toBe(true)
  })
})

function mountView() {
  return mount(MainView, {
    global: {
      stubs: {
        DeviceTree: { template: '<div class="device-tree-stub" />' },
        DeviceTable: {
          props: ['onEdit'],
          template: '<div class="device-table-stub"><button class="table-edit" @click="onEdit({ id: 2, name: \'核心交换机\', type: \'switch\', parent_id: 1, ip_address: \'10.0.0.1\', port: 22, location: \'机架1\' })">编辑</button></div>',
        },
        DeviceDetail: { template: '<div class="device-detail-stub" />' },
        TopologyView: { template: '<div class="topology-stub" />' },
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
        'el-tag': {
          inheritAttrs: false,
          emits: ['close'],
          template: '<span data-tag :type="$attrs.type" :size="$attrs.size" :class="$attrs.class"><slot /><button v-if="$attrs.closable !== undefined" class="tag-close" @click="$emit(\'close\')">移除</button></span>',
        },
        'el-tree': { template: '<div><slot /></div>' },
        'el-tabs': { template: '<div class="tabs"><slot /></div>' },
        'el-tab-pane': { template: '<div :data-label="$attrs.label"><slot /></div>' },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div v-if="modelValue" class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div>{{ $attrs.label }}<slot /></div>' },
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

function typeToggleButton(wrapper) {
  return wrapper.findAll('button').find((b) => b.text().startsWith('设备类型'))
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

describe('MainView 设备类型管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示类型管理，添加自定义类型', async () => {
    authState.role = 'admin'
    addTypeMock.mockResolvedValue()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('设备类型')
    await typeToggleButton(wrapper).trigger('click')
    await flushPromises()
    const addInput = wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))
    await addInput.setValue('nas2')
    const addBtn = wrapper.findAll('button').find((b) => b.text() === '添加')
    await addBtn.trigger('click')
    await flushPromises()
    expect(addTypeMock).toHaveBeenCalledWith('nas2')
  })

  it('删除自定义类型需确认', async () => {
    authState.role = 'admin'
    removeTypeMock.mockResolvedValue()
    confirmMock.mockResolvedValue()
    const wrapper = mountView()
    await flushPromises()
    await typeToggleButton(wrapper).trigger('click')
    await flushPromises()
    const removeBtn = wrapper.findAll('button').find((b) => b.text() === '移除')
    expect(removeBtn).toBeTruthy()
    await removeBtn.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(removeTypeMock).toHaveBeenCalledWith('nas2')
  })

  it('viewer 不显示类型管理', async () => {
    authState.role = 'viewer'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).not.toContain('设备类型')
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
    const collapsedContent = wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))
    expect(collapsedContent).toBeFalsy()
    await typeToggleButton(wrapper).trigger('click')
    await flushPromises()
    const addInput = wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))
    expect(addInput).toBeTruthy()
  })

  it('再次点击收起', async () => {
    authState.role = 'admin'
    const wrapper = mountView()
    await flushPromises()
    await typeToggleButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))).toBeTruthy()
    await typeToggleButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.findAll('input.t-input').find((i) => i.attributes('placeholder')?.includes('自定义类型名'))).toBeFalsy()
  })
})

describe('MainView ping 参数设置', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('admin 显示次数/包大小并可保存', async () => {
    authState.role = 'admin'
    savePingParamsMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('保存巡检参数')
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

describe('MainView 表格编辑设备', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('表格编辑按钮打开对话框并预填表单', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    const switchEl = wrapper.findComponent('.view-switch')
    switchEl.vm.$emit('update:modelValue', 'table')
    await flushPromises()
    await wrapper.find('.table-edit').trigger('click')
    await flushPromises()
    const inputs = wrapper.findAll('.dlg input')
    expect(inputs.find((i) => i.element.value === '核心交换机')).toBeTruthy()
    expect(inputs.find((i) => i.element.value === '10.0.0.1')).toBeTruthy()
  })

  it('保存时提交编辑数据', async () => {
    updateMock.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    const switchEl = wrapper.findComponent('.view-switch')
    switchEl.vm.$emit('update:modelValue', 'table')
    await flushPromises()
    await wrapper.find('.table-edit').trigger('click')
    await flushPromises()
    await wrapper.findAll('.dlg input.t-input').at(0).setValue('核心交换2')
    const saveBtns = wrapper.findAll('button').filter((b) => b.text() === '保存')
    await saveBtns.at(-1).trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(2, expect.objectContaining({
      name: '核心交换2',
      parent_id: 1,
      ip_address: '10.0.0.1',
      port: 22,
      location: '机架1',
    }))
    expect(successMock).toHaveBeenCalledWith('已保存')
  })
})
