// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  createMock,
  loadMock,
  loadMeMock,
  logoutMock,
  pushMock,
  promptMock,
  successMock,
  errorMock,
} = vi.hoisted(() => ({
  createMock: vi.fn(),
  loadMock: vi.fn(),
  loadMeMock: vi.fn(),
  logoutMock: vi.fn(),
  pushMock: vi.fn(),
  promptMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { prompt: promptMock },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    tree: [],
    stats: { online: 0, offline: 0, warning: 0, unknown: 0 },
    load: loadMock,
    create: createMock,
  }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({
    user: { username: 'admin', role: 'admin' },
    loadMe: loadMeMock,
    logout: logoutMock,
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

import MainView from '../MainView.vue'

function mountView() {
  return mount(MainView, {
    global: {
      stubs: {
        DeviceTree: { template: '<div class="device-tree-stub" />' },
        'el-container': { template: '<div><slot /></div>' },
        'el-header': { template: '<header><slot /></header>' },
        'el-main': { template: '<main><slot /></main>' },
        'el-card': { template: '<div><slot name="header" /><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-tree': { template: '<div><slot /></div>' },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

function rootButton(wrapper) {
  return wrapper.findAll('button').find((b) => b.text() === '新增根分组')
}

describe('MainView 新增根分组', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    promptMock.mockResolvedValue({ value: '研发部' })
  })

  it('点击后弹窗询问分组名，并以输入名称创建', async () => {
    const wrapper = mountView()
    await flushPromises()
    await rootButton(wrapper).trigger('click')
    expect(promptMock).toHaveBeenCalled()
    await flushPromises()
    expect(createMock).toHaveBeenCalledWith({ name: '研发部', type: 'group' })
  })

  it('创建失败（如同名被拒）时提示后端错误，不静默失败', async () => {
    createMock.mockRejectedValue({ response: { data: { detail: '已存在同名节点' } } })
    const wrapper = mountView()
    await flushPromises()
    await rootButton(wrapper).trigger('click')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('已存在同名节点')
  })
})
