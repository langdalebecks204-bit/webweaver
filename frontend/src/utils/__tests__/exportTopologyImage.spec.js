// @vitest-environment happy-dom
import { describe, it, expect, vi } from 'vitest'
import {
  calculateGraphBounds,
  exportFullTopologyImage,
} from '../exportTopologyImage'

describe('exportTopologyImage', () => {
  it('calculateGraphBounds 计算所有节点的正交外接矩形与安全内边距', () => {
    const nodes = [
      { x: -100, y: 50 },
      { x: 200, y: 300 },
      { x: 50, y: -50 },
    ]
    const bounds = calculateGraphBounds(nodes, 60)
    expect(bounds.minX).toBe(-100 - 60)
    expect(bounds.maxX).toBe(200 + 60)
    expect(bounds.minY).toBe(-50 - 60)
    expect(bounds.maxY).toBe(300 + 60)
    expect(bounds.width).toBe(300 + 120)
    expect(bounds.height).toBe(350 + 120)
  })

  it('空节点集合时 calculateGraphBounds 返回默认尺寸避免异常', () => {
    const bounds = calculateGraphBounds([])
    expect(bounds.width).toBeGreaterThan(0)
    expect(bounds.height).toBeGreaterThan(0)
  })

  it('exportFullTopologyImage 在无节点时直接返回 false', async () => {
    const result = await exportFullTopologyImage([], [])
    expect(result).toBe(false)
  })
})
