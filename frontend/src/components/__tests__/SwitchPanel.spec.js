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

  it('根据连接速率为端口设置对应的速率类和颜色', () => {
    const interfaces = [
      { if_index: 1, name: 'GE1', status: 'up', speed_mbps: 100, in_rate_text: '1M', out_rate_text: '1M' },
      { if_index: 2, name: 'GE2', status: 'up', speed_mbps: 1000, in_rate_text: '1M', out_rate_text: '1M' },
      { if_index: 3, name: 'GE3', status: 'up', speed_mbps: 2500, in_rate_text: '1M', out_rate_text: '1M' },
      { if_index: 4, name: 'GE4', status: 'up', speed_mbps: 10000, in_rate_text: '1M', out_rate_text: '1M' },
      { if_index: 5, name: 'GE5', status: 'down', speed_mbps: 0, in_rate_text: '0', out_rate_text: '0' },
    ]

    const wrapper = mount(SwitchPanel, {
      props: {
        deviceName: 'Core Switch',
        interfaces,
      },
      global: { stubs },
    })

    const ports = wrapper.findAll('.port-item')
    expect(ports.length).toBe(5)

    // 百兆: speed-100m, #f97316
    expect(ports[0].classes()).toContain('speed-100m')
    expect(ports[0].attributes('style')).toContain('#f97316')

    // 千兆: speed-100m, #10b981
    expect(ports[1].classes()).toContain('speed-1000m')
    expect(ports[1].attributes('style')).toContain('#10b981')

    // 2.5G: speed-2500m, #39ff14
    expect(ports[2].classes()).toContain('speed-2500m')
    expect(ports[2].attributes('style')).toContain('#39ff14')

    // 万兆: speed-10000m, #3b82f6
    expect(ports[3].classes()).toContain('speed-10000m')
    expect(ports[3].attributes('style')).toContain('#3b82f6')

    // 离线: speed-down
    expect(ports[4].classes()).toContain('speed-down')

    // 图例显示
    expect(wrapper.find('.speed-legend').exists()).toBe(true)
    expect(wrapper.text()).toContain('百兆')
    expect(wrapper.text()).toContain('千兆')
    expect(wrapper.text()).toContain('2.5G')
    expect(wrapper.text()).toContain('万兆')
  })
})
