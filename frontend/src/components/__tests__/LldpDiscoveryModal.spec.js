// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LldpDiscoveryModal from '../LldpDiscoveryModal.vue'

vi.mock('../../api/topology', () => ({
  default: {
    getLldpNeighbors: vi.fn(),
    applyLldp: vi.fn(),
    edgeDiscover: vi.fn(),
    applyEdge: vi.fn(),
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

  it('打开弹窗时默认在骨干互联页签，获取 LLDP 邻居与统计数据', async () => {
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
          ElTabs: {
            template: '<div><slot /></div>',
          },
          ElTabPane: {
            props: ['label', 'name'],
            template: '<div class="tab-pane-stub"><slot /></div>',
          },
          ElTable: true,
          ElTableColumn: true,
          ElTag: true,
          ElCollapse: true,
          ElCollapseItem: true,
          ElCheckbox: true,
          ElInput: {
            props: ['modelValue'],
            template: '<input class="el-input-stub" :value="modelValue" />',
          },
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

  it('点击应用骨干链路调用 applyLldp 并向外发出 applied 事件', async () => {
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
          ElTabs: {
            template: '<div><slot /></div>',
          },
          ElTabPane: {
            props: ['label', 'name'],
            template: '<div class="tab-pane-stub"><slot /></div>',
          },
          ElTable: true,
          ElTableColumn: true,
          ElTag: true,
          ElCollapse: true,
          ElCollapseItem: true,
          ElCheckbox: true,
          ElInput: {
            props: ['modelValue'],
            template: '<input class="el-input-stub" :value="modelValue" />',
          },
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

    const applyBtn = wrapper.findAll('button').find((b) => b.text().includes('一键固化应用骨干链路'))
    expect(applyBtn).toBeTruthy()
    await applyBtn.trigger('click')
    await flushPromises()

    expect(topologyApi.applyLldp).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('成功固化 2 个物理端口互联'))
    expect(wrapper.emitted('applied')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
  })

  it('边缘推导页签支持渲染直连设备、傻瓜交换机与无线 AP 收敛，并调用 applyEdge', async () => {
    topologyApi.getLldpNeighbors.mockResolvedValueOnce({
      data: { links: [], unmatched_neighbors: [], scanned_devices_count: 0 },
    })
    topologyApi.edgeDiscover.mockResolvedValueOnce({
      data: {
        direct_terminals: [
          {
            device_id: 10,
            switch_id: 1,
            switch_name: 'SW-Core',
            port_num: 5,
            port_name: 'GE5',
            device_name: 'PC-Finance-1',
            ip_address: '192.168.1.50',
            mac: '00:11:22:33:44:55',
            vendor: 'Dell',
          },
        ],
        unmanaged_hubs: [
          {
            switch_id: 1,
            switch_name: 'SW-Core',
            port_num: 8,
            port_name: 'GE8',
            suggested_name: 'SW-Core_P8_分线交换机',
            terminal_count: 2,
            attached_devices: [{ device_id: 20, name: 'PC-2', mac: '00:AA:BB:11:22:33' }],
            unregistered_assets: [],
          },
        ],
        ap_clusters: [
          {
            switch_id: 1,
            switch_name: 'SW-Core',
            port_num: 12,
            port_name: 'GE12',
            ap_name: 'AP-Meeting',
            mobile_count: 5,
          },
        ],
      },
    })
    topologyApi.applyEdge.mockResolvedValueOnce({
      data: { applied_direct_count: 1, created_hubs_count: 1 },
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
          ElTabs: {
            template: '<div><slot /></div>',
          },
          ElTabPane: {
            props: ['label', 'name'],
            template: '<div class="tab-pane-stub"><slot /></div>',
          },
          ElTable: true,
          ElTableColumn: true,
          ElTag: true,
          ElCollapse: true,
          ElCollapseItem: true,
          ElInput: {
            props: ['modelValue'],
            template: '<input class="el-input-stub" :value="modelValue" />',
          },
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

    // Switch tab to edge
    wrapper.vm.activeTab = 'edge'
    wrapper.vm.onTabChange('edge')
    await flushPromises()

    expect(topologyApi.edgeDiscover).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('直连有线终端：')
    expect(wrapper.text()).toContain('建议聚合分线器：')
    expect(wrapper.text()).toContain('收敛无线 AP：')
    expect(wrapper.find('input.el-input-stub').element.value).toBe('SW-Core_P8_分线交换机')
    expect(wrapper.text()).toContain('已识别并过滤 5 台手机/便携终端噪点')

    // Click apply edge button
    const applyEdgeBtn = wrapper.findAll('button').find((b) => b.text().includes('一键应用边缘接入'))
    expect(applyEdgeBtn).toBeTruthy()
    await applyEdgeBtn.trigger('click')
    await flushPromises()

    expect(topologyApi.applyEdge).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('成功应用边缘接入'))
    expect(wrapper.emitted('applied')).toBeTruthy()
  })
})
