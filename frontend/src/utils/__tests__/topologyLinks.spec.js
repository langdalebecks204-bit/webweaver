import { describe, it, expect } from 'vitest'
import { getLinkColor, SPEED_COLORS } from '../topologyLinks'

describe('topologyLinks - getLinkColor', () => {
  it('端点或链路离线时返回离线红色', () => {
    expect(getLinkColor({ status: 'offline' })).toBe(SPEED_COLORS.offline)
    expect(getLinkColor({ source: { status: 'offline' }, target: { status: 'online' } })).toBe(SPEED_COLORS.offline)
    expect(getLinkColor({ source: { status: 'online' }, target: { status: 'offline' } })).toBe(SPEED_COLORS.offline)
  })

  it('优先使用 SNMP 报告的实时速率', () => {
    const snmpMap = new Map([
      ['1->2', 1000],
      ['1->3', 10000],
      ['1->4', 2500],
      ['1->5', 100],
    ])

    expect(getLinkColor({ source: { id: 1 }, target: { id: 2 } }, snmpMap)).toBe(SPEED_COLORS[1000])
    expect(getLinkColor({ source: { id: 1 }, target: { id: 3 } }, snmpMap)).toBe(SPEED_COLORS[10000])
    expect(getLinkColor({ source: { id: 1 }, target: { id: 4 } }, snmpMap)).toBe(SPEED_COLORS[2500])
    expect(getLinkColor({ source: { id: 1 }, target: { id: 5 } }, snmpMap)).toBe(SPEED_COLORS[100])
  })

  it('SNMP无数据时回退到 port_bindings 自定义速率', () => {
    const link = {
      source: {
        id: 1,
        port_bindings: {
          '1': { target_id: 2, speed_mbps: 2500 },
        },
      },
      target: { id: 2 },
    }
    expect(getLinkColor(link)).toBe(SPEED_COLORS[2500])
  })

  it('未知速率返回灰色', () => {
    expect(getLinkColor({ source: { id: 1 }, target: { id: 2 } })).toBe(SPEED_COLORS.unknown)
  })
})
