// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { historyMock, uploadMock, deleteImageMock, successMock, errorMock, confirmMock } =
  vi.hoisted(() => ({
    historyMock: vi.fn(),
    uploadMock: vi.fn(),
    deleteImageMock: vi.fn(),
    successMock: vi.fn(),
    errorMock: vi.fn(),
    confirmMock: vi.fn(),
  }))

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: { success: successMock, error: errorMock },
    ElMessageBox: { confirm: confirmMock },
  }
})

vi.mock('../../api/devices', () => ({
  fetchDeviceHistory: historyMock,
  uploadDeviceImage: uploadMock,
  deleteDeviceImage: deleteImageMock,
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))

import DeviceDetail from '../DeviceDetail.vue'
import ElementPlus from 'element-plus'

const records = [
  { checked_at: '2026-08-01T00:00:00Z', status: 'online', latency_ms: 5 },
  { checked_at: '2026-08-02T00:00:00Z', status: 'offline', latency_ms: null },
  { checked_at: '2026-08-03T00:00:00Z', status: 'online', latency_ms: 8 },
  { checked_at: '2026-08-04T00:00:00Z', status: 'online', latency_ms: 6 },
]

const device = {
  id: 1,
  name: 'sw1',
  type: 'switch',
  ip_address: '10.0.0.1',
  port: 22,
  location: '机房A',
  status: 'online',
  latency_ms: 5,
  image_url: '/uploads/1.jpg',
}

function mountDetail() {
  return mount(DeviceDetail, {
    props: { device },
    global: {
      plugins: [ElementPlus],
      stubs: {
        'el-dialog': {
          props: ['modelValue'],
          template: '<div><slot /><slot name="footer" /></div>',
        },
        'el-tabs': { template: '<div><slot /></div>' },
        'el-tab-pane': { template: '<div><slot /></div>' },
        'el-button': {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

describe('DeviceDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    historyMock.mockResolvedValue({ data: { records } })
  })

  it('加载历史记录并展示基本信息', async () => {
    const wrapper = mountDetail()
    await flushPromises()
    expect(historyMock).toHaveBeenCalledWith(1, 30)
    expect(wrapper.text()).toContain('10.0.0.1')
    expect(wrapper.text()).toContain('机房A')
  })

  it('统计页正确计算上线/离线/在线率', async () => {
    const wrapper = mountDetail()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('在线率')
    expect(text).toContain('3')
    expect(text).toContain('1')
    expect(text).toContain('75%')
  })

  it('admin 可上传图片', async () => {
    uploadMock.mockResolvedValue({ data: { id: 1, image_url: '/uploads/1.jpg' } })
    const wrapper = mountDetail()
    await flushPromises()
    const buttons = wrapper.findAll('button')
    await buttons.find((b) => b.text() === '上传/更换').trigger('click')
    const input = wrapper.find('input[type=file]')
    const file = new File(['x'], 'pic.png', { type: 'image/png' })
    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    await flushPromises()
    expect(uploadMock).toHaveBeenCalled()
  })

  it('admin 删除图片需确认', async () => {
    confirmMock.mockResolvedValue()
    deleteImageMock.mockResolvedValue({ data: { id: 1, image_url: null } })
    const wrapper = mountDetail()
    await flushPromises()
    const buttons = wrapper.findAll('button')
    await buttons.find((b) => b.text() === '删除').trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(deleteImageMock).toHaveBeenCalledWith(1)
  })

  it('上传失败提示后端错误', async () => {
    historyMock.mockResolvedValue({ data: { records: [] } })
    uploadMock.mockRejectedValue({ response: { data: { detail: '仅支持图片' } } })
    const wrapper = mountDetail()
    await flushPromises()
    const input = wrapper.find('input[type=file]')
    const file = new File(['bad'], 'x.txt', { type: 'text/plain' })
    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    await flushPromises()
    expect(errorMock).toHaveBeenCalledWith('仅支持图片')
  })
})