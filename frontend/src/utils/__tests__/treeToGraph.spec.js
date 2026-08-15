import { describe, it, expect } from 'vitest'
import { treeToGraph } from '../treeToGraph'

const tree = [
  {
    id: 1,
    name: '机房A',
    type: 'group',
    status: 'online',
    parent_id: null,
    children: [
      {
        id: 2,
        name: '核心交换机',
        type: 'switch',
        status: 'online',
        latency_ms: 5,
        ip_address: '10.0.0.1',
        parent_id: 1,
        children: [],
      },
      {
        id: 3,
        name: '终端B',
        type: 'terminal',
        status: 'offline',
        latency_ms: null,
        ip_address: '10.0.0.2',
        parent_id: 1,
        children: [],
      },
    ],
  },
]

describe('treeToGraph', () => {
  it('树打平为节点与链接', () => {
    const { nodes, links } = treeToGraph(tree)
    expect(nodes.map((n) => n.id).sort()).toEqual([1, 2, 3])
    expect(links).toContainEqual({ source: 1, target: 2, status: 'online' })
    expect(links).toContainEqual({ source: 1, target: 3, status: 'offline' })
  })

  it('分组节点状态强制 unknown 且权重随子节点数', () => {
    const { nodes } = treeToGraph(tree)
    const group = nodes.find((n) => n.id === 1)
    expect(group.status).toBe('unknown')
    expect(group.val).toBe(2 * 3 + 8)
    const leaf = nodes.find((n) => n.id === 2)
    expect(leaf.val).toBe(8)
  })

  it('空树返回空', () => {
    expect(treeToGraph([])).toEqual({ nodes: [], links: [] })
  })
})