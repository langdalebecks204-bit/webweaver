// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AssetsPanel from '../AssetsPanel.vue'
import { useAssetsStore } from '../../stores/assets'
import { useAuthStore } from '../../stores/auth'

vi.mock('../../api/assets', () => ({
  default: {
    getAssets: vi.fn().mockResolvedValue({ data: [] }),
    scanAssets: vi.fn().mockResolvedValue({ data: [] }),
    enrollAsset: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

const stubs = {
  ElSelect: {
    template: '<div><slot /></div>',
    props: ['modelValue'],
  },
  ElOption: {
    template: '<option><slot /></option>',
    props: ['label', 'value'],
  },
  ElInput: {
    template: '<input :value="modelValue" />',
    props: ['modelValue'],
  },
  ElButton: {
    template: '<button><slot /></button>',
  },
  ElTable: {
    template: '<div class="el-table"><slot /></div>',
    props: ['data'],
  },
  ElTableColumn: {
    template: '<div class="el-table-column"><slot :row="row" /></div>',
    props: ['prop', 'label'],
    data() {
      return { row: {} }
    },
  },
  ElTag: {
    template: '<span class="el-tag"><slot /></span>',
    props: ['type'],
  },
  ElDialog: {
    template: '<div v-if="modelValue" class="el-dialog"><slot /><slot name="footer" /></div>',
    props: ['modelValue'],
  },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<div><slot /></div>' },
}

describe('AssetsPanel.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染统计卡片与资产列表', async () => {
    const assetsStore = useAssetsStore()
    const authStore = useAuthStore()
    authStore.user = { username: 'admin', role: 'admin' }

    assetsStore.items = [
      {
        ip: '192.168.1.50',
        mac: '48:2C:6A:11:22:33',
        vendor: 'Apple',
        if_name: 'GE0/1',
        collector_device_name: 'CoreSwitch',
        is_managed: true,
        managed_device_name: 'CEO-MacBook',
        managed_device_type: 'server',
      },
      {
        ip: '192.168.1.120',
        mac: '44:19:B6:55:66:77',
        vendor: 'Hikvision',
        if_name: 'GE0/2',
        collector_device_name: 'CoreSwitch',
        is_managed: false,
        managed_device_name: null,
        managed_device_type: null,
      },
    ]

    const wrapper = mount(AssetsPanel, {
      global: { stubs },
    })

    expect(wrapper.text()).toContain('全网活跃 IP / MAC')
    expect(wrapper.text()).toContain('已纳管设备')
    expect(wrapper.text()).toContain('未登记终端（待纳管）')
    expect(wrapper.find('.stat-value.total').text()).toBe('2')
    expect(wrapper.find('.stat-value.managed').text()).toBe('1')
    expect(wrapper.find('.stat-value.unmanaged').text()).toBe('1')
  })

  it('根据关键词搜索与状态筛选进行过滤', async () => {
    const assetsStore = useAssetsStore()
    assetsStore.items = [
      { ip: '10.0.0.1', mac: '00:00:0C:01:02:03', vendor: 'Cisco', is_managed: true },
      { ip: '192.168.1.88', mac: '70:79:90:AA:BB:CC', vendor: 'Huawei', is_managed: false },
    ]

    const wrapper = mount(AssetsPanel, {
      global: { stubs },
    })

    // Initial unfiltered
    expect(wrapper.vm.filteredAssets.length).toBe(2)

    // Filter by keyword
    wrapper.vm.keyword = '192.168'
    expect(wrapper.vm.filteredAssets.length).toBe(1)
    expect(wrapper.vm.filteredAssets[0].ip).toBe('192.168.1.88')

    // Filter by unmanaged
    wrapper.vm.keyword = ''
    wrapper.vm.managedFilter = 'unmanaged'
    expect(wrapper.vm.filteredAssets.length).toBe(1)
    expect(wrapper.vm.filteredAssets[0].vendor).toBe('Huawei')
  })

  it('打开一键纳管弹窗并预填信息', async () => {
    const assetsStore = useAssetsStore()
    const wrapper = mount(AssetsPanel, {
      global: { stubs },
    })

    const targetItem = {
      ip: '192.168.1.200',
      mac: '44:19:B6:11:22:33',
      vendor: 'Hikvision',
      collector_device_id: 5,
    }

    wrapper.vm.openEnrollDialog(targetItem)
    expect(wrapper.vm.enrollDialogVisible).toBe(true)
    expect(wrapper.vm.enrollForm.ip_address).toBe('192.168.1.200')
    expect(wrapper.vm.enrollForm.mac_address).toBe('44:19:B6:11:22:33')
    expect(wrapper.vm.enrollForm.type).toBe('camera') // Auto guessed Hikvision camera!
    expect(wrapper.vm.enrollForm.parent_id).toBe(5)
  })
})
