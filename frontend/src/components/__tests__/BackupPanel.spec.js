// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  exportMock,
  importMock,
  resetMock,
  successMock,
  errorMock,
  promptMock,
  loadMock,
  extLoadMock,
  loadIntervalMock,
  logoutMock,
  pushMock,
} = vi.hoisted(() => ({
  exportMock: vi.fn(),
  importMock: vi.fn(),
  resetMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  promptMock: vi.fn(),
  loadMock: vi.fn(),
  extLoadMock: vi.fn(),
  loadIntervalMock: vi.fn(),
  logoutMock: vi.fn(),
  pushMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: successMock, error: errorMock },
  ElMessageBox: { prompt: promptMock },
}))

vi.mock('../../api/backup', () => ({
  exportBackup: exportMock,
  importBackup: importMock,
  resetData: resetMock,
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({ load: loadMock }),
}))

vi.mock('../../stores/external', () => ({
  useExternalStore: () => ({ load: extLoadMock }),
}))

vi.mock('../../stores/settings', () => ({
  useSettingsStore: () => ({ loadInterval: loadIntervalMock }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' }, logout: logoutMock }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

import BackupPanel from '../BackupPanel.vue'

function mountPanel() {
  return mount(BackupPanel, {
    global: {
      stubs: {
        'el-card': { template: '<div><slot name="header" /><slot /></div>' },
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

describe('BackupPanel 备份与恢复', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('导出默认勾选全部三类', async () => {
    exportMock.mockResolvedValue({ data: { version: 1 } })
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '导出备份').trigger('click')
    await flushPromises()
    expect(exportMock).toHaveBeenCalledWith({
      include_devices: true,
      include_external: true,
      include_settings: true,
    })
  })

  it('取消勾选外网后导出参数排除外网', async () => {
    exportMock.mockResolvedValue({ data: { version: 1 } })
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(false)
    await buttonByText(wrapper, '导出备份').trigger('click')
    await flushPromises()
    expect(exportMock).toHaveBeenCalledWith({
      include_devices: true,
      include_external: false,
      include_settings: true,
    })
  })

  it('导入上传文件后调用 import 并刷新数据', async () => {
    importMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    const file = new File([JSON.stringify({ version: 1 })], 'backup.json',
                          { type: 'application/json' })
    const input = wrapper.find('input.file-input')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    await flushPromises()
    expect(importMock).toHaveBeenCalledWith({ version: 1 }, 'replace')
    expect(loadMock).toHaveBeenCalled()
    expect(extLoadMock).toHaveBeenCalled()
    expect(successMock).toHaveBeenCalledWith('导入成功')
  })

  it('清除所有数据需输入 clear 确认后登出跳转', async () => {
    promptMock.mockResolvedValue({ value: 'clear' })
    resetMock.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '清除所有数据（初始化）').trigger('click')
    await flushPromises()
    expect(resetMock).toHaveBeenCalled()
    expect(logoutMock).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })

  it('清除取消时不做任何事', async () => {
    promptMock.mockRejectedValue('cancel')
    const wrapper = mountPanel()
    await flushPromises()
    await buttonByText(wrapper, '清除所有数据（初始化）').trigger('click')
    await flushPromises()
    expect(resetMock).not.toHaveBeenCalled()
  })
})