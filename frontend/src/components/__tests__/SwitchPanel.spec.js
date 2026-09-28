// @vitest-environment happy-dom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SwitchPanel from '../SwitchPanel.vue'

const stubs = {
  ElTag: { template: '<span><slot /></span>' },
  ElDivider: { template: '<hr />' },
}

describe('SwitchPanel', () => {
  it('渲染端口矩阵及自定义说明', () => {
    const interfaces = [
      {
        if_index: 1,
        name: 'GE0/1',
        status: 'up',
        speed_mbps: 1000,
        in_rate_text: '10 Mbps',
        out_rate_text: '5 Mbps',
        custom_description: '[上联] 核心交换机 (机房主干)',
      },
      {
        if_index: 2,
        name: 'GE0/2',
        status: 'down',
        speed_mbps: 0,
        in_rate_text: '0 bps',
        out_rate_text: '0 bps',
        custom_description: '',
      },
    ]

    const wrapper = mount(SwitchPanel, {
      props: {
        deviceName: 'Test Switch',
        interfaces,
        selectedPortIndex: 1,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('Test Switch')
    const tooltips = wrapper.findAll('.port-tooltip')
    expect(tooltips.length).toBe(2)
    expect(tooltips[0].text()).toContain('[上联] 核心交换机 (机房主干)')
    expect(tooltips[1].find('.tooltip-desc').exists()).toBe(false)
  })
})
