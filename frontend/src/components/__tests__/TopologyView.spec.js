// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

let fgMock
const createMock = vi.hoisted(() => vi.fn())

vi.mock('force-graph', () => ({ default: createMock }))

const treeMock = vi.hoisted(() => [
  {
    id: 1,
    name: '机房A',
    type: 'group',
    status: 'unknown',
    parent_id: null,
    children: [],
  },
])

vi.mock('../../stores/devices', () => ({
  useDevicesStore: () => ({ tree: treeMock }),
}))

import TopologyView from '../TopologyView.vue'

describe('TopologyView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    treeMock.splice(0, treeMock.length, {
      id: 1,
      name: '机房A',
      type: 'group',
      status: 'unknown',
      parent_id: null,
      children: [],
    })
    fgMock = {
      backgroundColor: vi.fn(() => fgMock),
      graphData: vi.fn(() => fgMock),
      nodeRelSize: vi.fn(() => fgMock),
      nodeCanvasObjectMode: vi.fn(() => fgMock),
      nodeCanvasObject: vi.fn(() => fgMock),
      linkColor: vi.fn(() => fgMock),
      linkDirectionalParticles: vi.fn(() => fgMock),
      linkDirectionalParticleSpeed: vi.fn(() => fgMock),
      linkDirectionalParticleWidth: vi.fn(() => fgMock),
      linkDirectionalParticleColor: vi.fn(() => fgMock),
      onNodeHover: vi.fn(() => fgMock),
      width: vi.fn(() => fgMock),
      height: vi.fn(() => fgMock),
      destroy: vi.fn(() => fgMock),
    }
    createMock.mockReturnValue(fgMock)
  })

  it('挂载时创建图谱并设置数据与特效', async () => {
    mount(TopologyView)
    await flushPromises()
    expect(createMock).toHaveBeenCalledTimes(1)
    expect(fgMock.graphData).toHaveBeenCalledTimes(1)
    expect(fgMock.backgroundColor).toHaveBeenCalledWith('#0f172a')
    expect(fgMock.nodeCanvasObjectMode).toHaveBeenCalled()
    expect(fgMock.nodeCanvasObject).toHaveBeenCalled()
    expect(fgMock.onNodeHover).toHaveBeenCalled()
    expect(fgMock.linkDirectionalParticles).toHaveBeenCalled()
    expect(fgMock.linkDirectionalParticleSpeed).toHaveBeenCalled()
    expect(fgMock.linkDirectionalParticleColor).toHaveBeenCalled()
  })

  it('空树时显示空态提示且不创建图谱', async () => {
    treeMock.splice(0, treeMock.length)
    const wrapper = mount(TopologyView)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无设备')
    expect(createMock).not.toHaveBeenCalled()
  })
})