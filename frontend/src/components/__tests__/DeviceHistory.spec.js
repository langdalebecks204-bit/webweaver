// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { fetchMock, setOptionMock, resizeMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  setOptionMock: vi.fn(),
  resizeMock: vi.fn(),
}))

vi.mock('echarts', () => ({
  init: () => ({
    setOption: setOptionMock,
    resize: resizeMock,
    dispose: vi.fn(),
  }),
}))

vi.mock('../../api/devices', () => ({
  fetchDeviceHistory: fetchMock,
}))

import DeviceHistory from '../DeviceHistory.vue'

const device = { id: 1, name: 'sw' }

function mountComp(props = { device }) {
  return mount(DeviceHistory, {
    props,
    global: {
      stubs: {
        'el-dialog': {
          props: ['modelValue'],
          template: '<div class="dlg"><slot /><slot name="footer" /></div>',
        },
        'el-radio-group': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<div class="rg"><slot /></div>',
        },
        'el-radio-button': {
          props: ['value'],
          template: '<button class="rb"><slot /></button>',
        },
        'el-select': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value))"><slot /></select>',
        },
        'el-option': {
          props: ['value'],
          template: '<option :value="value"><slot /></option>',
        },
        'el-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

describe('DeviceHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchMock.mockResolvedValue({
      data: {
        device_id: 1,
        records: [
          { checked_at: '2026-08-01T10:00:00', status: 'online', latency_ms: 8 },
          { checked_at: '2026-08-01T10:05:00', status: 'online', latency_ms: 12 },
          { checked_at: '2026-08-01T11:00:00', status: 'offline', latency_ms: null },
        ],
      },
    })
  })

  it('挂载后拉取历史并渲染柱状图（默认 7 天、hour 粒度）', async () => {
    mountComp()
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(1, 7)
    expect(setOptionMock).toHaveBeenCalled()
    const arg = setOptionMock.mock.calls[0][0]
    expect(arg.xAxis.data).toContain('2026-08-01 10:00')
    expect(arg.series[0].data).toContain(10)
  })

  it('切换范围重新拉取', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fetchMock.mockClear()
    await wrapper.find('select').setValue('30')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(1, 30)
  })
})
