import { describe, it, expect } from 'vitest'
import { flattenTree, filterDevices } from '../devicesHelpers'

const tree = [
  {
    id: 1,
    name: '机房A',
    type: 'group',
    parent_id: null,
    location: null,
    status: 'unknown',
    children: [
      {
        id: 2,
        name: '核心交换机',
        type: 'switch',
        parent_id: 1,
        ip_address: '10.0.0.1',
        location: '机架1',
        status: 'online',
        children: [],
      },
      {
        id: 3,
        name: '终端B',
        type: 'terminal',
        parent_id: 1,
        ip_address: '10.0.0.2',
        location: null,
        status: 'offline',
        children: [],
      },
    ],
  },
]

describe('flattenTree', () => {
  it('展开树并为节点推导父级全名', () => {
    const flat = flattenTree(tree)
    expect(flat).toHaveLength(3)
    const byId = Object.fromEntries(flat.map((n) => [n.id, n]))
    expect(byId[2].parentName).toBe('机房A')
    expect(byId[3].parentName).toBe('机房A')
    expect(byId[1].parentName).toBe('')
  })
})

describe('filterDevices', () => {
  const flat = flattenTree(tree)

  it('按名称关键字过滤', () => {
    expect(filterDevices(flat, { keyword: '终端' })).toHaveLength(1)
  })

  it('按 IP 过滤', () => {
    expect(filterDevices(flat, { keyword: '10.0.0.1' })).toHaveLength(1)
  })

  it('按位置过滤', () => {
    expect(filterDevices(flat, { keyword: '机架1' })).toHaveLength(1)
  })

  it('按状态过滤', () => {
    expect(filterDevices(flat, { status: 'online' })).toHaveLength(1)
    expect(filterDevices(flat, { status: 'unknown' })).toHaveLength(1)
  })

  it('关键字与状态组合过滤', () => {
    expect(filterDevices(flat, { keyword: '终端', status: 'offline' })).toHaveLength(1)
    expect(filterDevices(flat, { keyword: '终端', status: 'online' })).toHaveLength(0)
  })
})