// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'

let fgMock
const createMock = vi.hoisted(() => vi.fn())
let lastCallWasNew

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
    let graphStore = { nodes: [], links: [] }
    fgMock = {
      backgroundColor: vi.fn(() => fgMock),
      graphData: vi.fn((...args) => {
        if (args.length) {
          graphStore = args[0]
          return fgMock
        }
        return graphStore
      }),
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
    createMock.mockImplementation(function () {
      lastCallWasNew = this instanceof createMock
      return fgMock
    })
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
  })

  it('挂载时创建图谱并设置数据与特效', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    expect(createMock).toHaveBeenCalledTimes(1)
    expect(lastCallWasNew).toBe(true)
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
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无设备')
    expect(createMock).not.toHaveBeenCalled()
  })

  it('数据异步加载完成后创建图谱', async () => {
    treeMock.splice(0, treeMock.length)
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
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

  it('标签字号可调整且影响绘制', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    const draw = fgMock.nodeCanvasObject.mock.calls[0][0]
    const ctx = { fillStyle: '', font: '', textAlign: '', fillText: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(), globalAlpha: 1, shadowColor: '', shadowBlur: 0 }
    const node = { id: 3, name: '节点C', type: 'terminal', status: 'online', val: 8, x: 10, y: 10 }
    draw(node, ctx)
    expect(ctx.font).toBe('6px sans-serif')
    // 修改字号
    const slider = wrapper.findComponent({ name: 'ElSlider' })
    expect(slider.exists()).toBe(true)
    wrapper.vm.labelFontSize = 14
    await flushPromises()
    draw(node, ctx)
    expect(ctx.font).toBe('14px sans-serif')
  })

  it('隐藏标签时非悬停节点不显示文字，悬停节点仍显示', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    const draw = fgMock.nodeCanvasObject.mock.calls[0][0]
    const ctx = { fillStyle: '', font: '', textAlign: '', fillText: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(), globalAlpha: 1, shadowColor: '', shadowBlur: 0 }
    const node = { id: 3, name: '节点C', type: 'terminal', status: 'online', val: 8, x: 10, y: 10 }
    wrapper.vm.showLabels = false
    await flushPromises()
    draw(node, ctx)
    expect(ctx.fillText).not.toHaveBeenCalledWith('节点C', 10, expect.any(Number))
    // 模拟悬停
    fgMock.onNodeHover.mock.calls[0][0](node)
    draw(node, ctx)
    expect(ctx.fillText).toHaveBeenCalledWith('节点C', 10, expect.any(Number))
  })

  it('拓扑图页渲染字号滑块与显示标签开关', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    expect(wrapper.find('.topo-toolbar').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ElSlider' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ElSwitch' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('字号')
    expect(wrapper.text()).toContain('显示标签')
  })

  it('容器尺寸变化时同步画布尺寸', async () => {
    let observerCb = null
    const RealResizeObserver = window.ResizeObserver
    window.ResizeObserver = class {
      constructor(cb) {
        observerCb = cb
      }
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    try {
      wrapper = mount(TopologyView, {
        global: { stubs: { ElSlider: true, ElSwitch: true } },
      })
      await flushPromises()
      expect(createMock).toHaveBeenCalledTimes(1)
      const graph = wrapper.find('.graph').element
      Object.defineProperty(graph, 'clientWidth', { value: 900, configurable: true })
      Object.defineProperty(graph, 'clientHeight', { value: 600, configurable: true })
      observerCb([], {})
      await flushPromises()
      expect(fgMock.width).toHaveBeenCalledWith(900)
      expect(fgMock.height).toHaveBeenCalledWith(600)
    } finally {
      window.ResizeObserver = RealResizeObserver
    }
  })

  it('悬停节点不重置图数据', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    const before = fgMock.graphData.mock.calls.length
    fgMock.onNodeHover.mock.calls[0][0]({ id: 1 })
    await flushPromises()
    expect(fgMock.graphData.mock.calls.length).toBe(before)
  })

  it('轮询刷新时复用节点对象保留坐标', async () => {
    treeMock.splice(0, treeMock.length, {
      id: 5,
      name: '核心交换机',
      type: 'switch',
      status: 'online',
      latency_ms: 3,
      ip_address: '10.0.0.5',
      parent_id: null,
      children: [],
    })
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    const first = fgMock.graphData.mock.calls[0][0]
    first.nodes[0].x = 123
    first.nodes[0].y = -45
    store().tree[0].status = 'offline'
    await flushPromises()
    const last = fgMock.graphData.mock.calls.at(-1)[0]
    expect(last.nodes[0]).toBe(first.nodes[0])
    expect(last.nodes[0].x).toBe(123)
    expect(last.nodes[0].status).toBe('offline')
  })

  it('节点为大圆点并居中绘制类型图标', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    const draw = fgMock.nodeCanvasObject.mock.calls[0][0]
    const baselines = []
    const ctx = {
      get textBaseline() {
        return this._tb
      },
      set textBaseline(v) {
        baselines.push(v)
        this._tb = v
      },
      fillStyle: '', font: '', textAlign: '',
      fillText: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(),
      globalAlpha: 1, shadowColor: '', shadowBlur: 0,
    }
    const node = { id: 3, name: '核心交换机', type: 'switch', status: 'online', val: 8, x: 50, y: 60 }
    draw(node, ctx)
    expect(ctx.arc).toHaveBeenCalledWith(50, 60, 8, 0, 2 * Math.PI, false)
    expect(baselines).toContain('middle')
    expect(ctx.fillText).toHaveBeenCalledWith('🔀', 50, 60)
  })

  it('点击全屏按钮请求全屏，进入全屏后显示返回主页链接', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    const wrapEl = wrapper.find('.topology-wrap').element
    const reqSpy = vi.fn()
    wrapEl.requestFullscreen = reqSpy
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => null,
    })
    expect(wrapper.find('.back-home').exists()).toBe(false)
    await wrapper.find('.fullscreen-btn').trigger('click')
    expect(reqSpy).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => wrapEl,
    })
    document.dispatchEvent(new Event('fullscreenchange'))
    await flushPromises()
    expect(wrapper.find('.back-home').exists()).toBe(true)
  })

  it('返回主页退出全屏并向外发出 back-home', async () => {
    wrapper = mount(TopologyView, {
      global: { stubs: { ElSlider: true, ElSwitch: true } },
    })
    await flushPromises()
    const wrapEl = wrapper.find('.topology-wrap').element
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => wrapEl,
    })
    document.dispatchEvent(new Event('fullscreenchange'))
    await flushPromises()
    const exitSpy = vi.fn()
    document.exitFullscreen = exitSpy
    await wrapper.find('.back-home').trigger('click')
    expect(exitSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('back-home')).toBeTruthy()
  })
})