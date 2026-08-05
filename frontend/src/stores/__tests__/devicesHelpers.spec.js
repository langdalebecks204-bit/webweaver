import { describe, it, expect } from 'vitest'
import { updateStatus, removeNode } from '../devicesHelpers'

const tree = [
  {
    id: 1,
    name: 'root',
    children: [
      { id: 2, name: 'sw', status: 'unknown', children: [] },
      { id: 3, name: 'pc', status: 'unknown', children: [] },
    ],
  },
]

describe('updateStatus', () => {
  it('updates a nested node without mutating input', () => {
    const next = updateStatus(tree, 2, { status: 'online', latencyMs: 5 })
    expect(next[0].children[0]).toMatchObject({ id: 2, status: 'online', latencyMs: 5 })
    expect(next[0].children[1].status).toBe('unknown')
    expect(tree[0].children[0].status).toBe('unknown')
  })
})

describe('removeNode', () => {
  it('removes a nested node', () => {
    const next = removeNode(tree, 3)
    expect(next[0].children.map((n) => n.id)).toEqual([2])
  })
})
