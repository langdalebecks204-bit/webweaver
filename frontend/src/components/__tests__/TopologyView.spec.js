// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'

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
  useDevicesStore: () => reactive({ tree: reactive(treeMock) }),
}))

import TopologyView from '../TopologyView.vue'
import { useDevicesStore } from '../../stores/devices'

function store() {
  return useDevicesStore()
}

describe('TopologyView', () => {
  let wrapper
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

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
  })

  it('挂载时创建图谱并设置数据与特效', async () => {
    wrapper = mount(TopologyView)
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
    wrapper = mount(TopologyView)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无设备')
    expect(createMock).not.toHaveBeenCalled()
  })

  it('数据异步加载完成后创建图谱', async () => {
    treeMock.splice(0, treeMock.length)
    wrapper = mount(TopologyView)
    await flushPromises()
    expect(createMock).not.toHaveBeenCalled()
    store().tree.push({
      id: 2,
      name: '核心交换机',
      type: 'switch',
      status: 'online',
      latency_ms: 5,
      ip_address: '10.0.0.1',
      parent_id: null,
      children: [],
    })
    await flushPromises()
    expect(createMock).toHaveBeenCalledTimes(1)
    expect(fgMock.graphData).toHaveBeenCalledTimes(1)
  })
})