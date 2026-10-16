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
    expect(links).toContainEqual({ source: 1, target: 2, status: 'online', source_port: null, target_port: null })
    expect(links).toContainEqual({ source: 1, target: 3, status: 'offline', source_port: null, target_port: null })
  })

  it('提取父子端口绑定作为连线端口号', () => {
    const portTree = [
      {
        id: 1,
        name: '核心SW',
        type: 'switch',
        port_count: 24,
        port_bindings: {
          '1': { target_id: 2, type: 'downlink' },
        },
        children: [
          {
            id: 2,
            name: '接入SW',
            type: 'switch',
            port_count: 24,
            uplink_port: 24,
            port_bindings: {},
            children: [],
          },
        ],
      },
    ]
    const { links } = treeToGraph(portTree)
    expect(links.length).toBe(1)
    expect(links[0].source_port).toBe('P1')
    expect(links[0].target_port).toBe('P24')
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
    const res = treeToGraph([])
    expect(res.nodes).toEqual([])
    expect(res.links).toEqual([])
  })

  it('识别核心交换机并将节点排布为以核心为中心的分层同心圆', () => {
    const topologyTree = [
      {
        id: 1,
        name: '机房A',
        type: 'group',
        parent_id: null,
        children: [
          {
            id: 2,
            name: '核心交换机',
            type: 'switch',
            parent_id: 1,
            children: [
              {
                id: 3,
                name: '楼层交换机1',
                type: 'switch',
                parent_id: 2,
                children: [
                  {
                    id: 4,
                    name: 'PC-1',
                    type: 'terminal',
                    parent_id: 3,
                    children: [],
                  },
                ],
              },
            ],
          },
        ],
      },
    ]

    const { nodes, coreNodeId } = treeToGraph(topologyTree)
    expect(coreNodeId).toBe(2)

    const core = nodes.find((n) => n.id === 2)
    expect(core.fx).toBe(0)
    expect(core.fy).toBe(0)
    expect(core.layer).toBe(0)

    // 直连核心的节点（机房A为上级、楼层交换机1为下级）应处于内圈 layer 1
    const groupA = nodes.find((n) => n.id === 1)
    const floorSw = nodes.find((n) => n.id === 3)
    expect(groupA.layer).toBe(1)
    expect(floorSw.layer).toBe(1)
    const r1 = Math.round(Math.hypot(groupA.fx, groupA.fy))
    expect(r1).toBe(220)

    // PC-1 距离核心为 2 跳，应处于外圈 layer 2
    const pc = nodes.find((n) => n.id === 4)
    expect(pc.layer).toBe(2)
    const r2 = Math.round(Math.hypot(pc.fx, pc.fy))
    expect(r2).toBe(420)
  })
})