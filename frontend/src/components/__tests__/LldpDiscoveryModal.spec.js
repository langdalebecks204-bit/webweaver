// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LldpDiscoveryModal from '../LldpDiscoveryModal.vue'

vi.mock('../../api/topology', () => ({
  default: {
    getLldpNeighbors: vi.fn(),
    applyLldp: vi.fn(),
  },
}))

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({
    load: vi.fn().mockResolvedValue(),
  }),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

import topologyApi from '../../api/topology'
import { ElMessage } from 'element-plus'

describe('LldpDiscoveryModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('打开弹窗时自动获取 LLDP 邻居与统计数据', async () => {
    topologyApi.getLldpNeighbors.mockResolvedValueOnce({
      data: {
        scanned_devices_count: 2,
        links: [
          {
            source_device_id: 1,
            source_name: 'Core-SW',
            source_port: 'GE0/0/1',
            target_device_id: 2,
            target_name: 'Access-SW',
            target_port: 'GE0/0/24',
            is_bidirectional: true,
          },
        ],
        unmatched_neighbors: [
          {
            collector_device_name: 'Core-SW',
            local_port: 'GE0/0/10',
            remote_sys_name: 'External-AP',
            remote_chassis_id: 'aa:bb:cc:dd:ee:ff',
          },
        ],
      },
    })

    const wrapper = mount(LldpDiscoveryModal, {
      props: {
        modelValue: true,
      },
      global: {
        stubs: {
          ElDialog: {
            props: ['modelValue'],
            template: '<div v-if="modelValue" class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          },
          ElTable: true,
          ElTableColumn: true,
          ElTag: true,
          ElCollapse: true,
          ElCollapseItem: true,
          ElCheckbox: true,
          ElButton: {
            template: '<button><slot /></button>',
          },
        },
        directives: {
          loading: () => {},
        },
      },
    })

    await flushPromises()
    expect(topologyApi.getLldpNeighbors).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('2 台')
    expect(wrapper.text()).toContain('1 条链路')
    expect(wrapper.text()).toContain('1 个')
  })

  it('点击应用互联拓扑到平台调用 applyLldp 并向外发出 applied 事件', async () => {
    topologyApi.getLldpNeighbors.mockResolvedValueOnce({
      data: {
        scanned_devices_count: 1,
        links: [
          {
            source_device_id: 1,
            source_name: 'Core-SW',
            source_port: 'GE0/0/1',
            target_device_id: 2,
            target_name: 'Access-SW',
            target_port: 'GE0/0/24',
          },
        ],
        unmatched_neighbors: [],
      },
    })
    topologyApi.applyLldp.mockResolvedValueOnce({
      data: { applied_count: 2 },
    })

    const wrapper = mount(LldpDiscoveryModal, {
      props: {
        modelValue: true,
      },
      global: {
        stubs: {
          ElDialog: {
            props: ['modelValue'],
            template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
          },
          ElTable: true,
          ElTableColumn: true,
          ElTag: true,
          ElCollapse: true,
          ElCollapseItem: true,
          ElCheckbox: true,
          ElButton: {
            template: '<button><slot /></button>',
          },
        },
        directives: {
          loading: () => {},
        },
      },
    })

    await flushPromises()

    const applyBtn = wrapper.findAll('button').find((b) => b.text().includes('一键固化应用到拓扑'))
    expect(applyBtn).toBeTruthy()
    await applyBtn.trigger('click')
    await flushPromises()

    expect(topologyApi.applyLldp).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('成功固化 2 个物理端口互联'))
    expect(wrapper.emitted('applied')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
  })
})
