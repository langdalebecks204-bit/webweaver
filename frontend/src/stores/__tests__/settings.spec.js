import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { fetchMock, updateMock, fetchTypesMock, addTypeMock, removeTypeMock, fetchPingMock, updatePingMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  updateMock: vi.fn(),
  fetchTypesMock: vi.fn(),
  addTypeMock: vi.fn(),
  removeTypeMock: vi.fn(),
  fetchPingMock: vi.fn(),
  updatePingMock: vi.fn(),
}))

vi.mock('../../api/settings', () => ({
  fetchInspectionInterval: fetchMock,
  updateInspectionInterval: updateMock,
  fetchDeviceTypes: fetchTypesMock,
  addDeviceType: addTypeMock,
  removeDeviceType: removeTypeMock,
  fetchPingParams: fetchPingMock,
  updatePingParams: updatePingMock,
}))

import { useSettingsStore } from '../settings'

describe('settings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadInterval fetches current interval', async () => {
    fetchMock.mockResolvedValue({ data: { poll_interval_minutes: 30 } })
    const store = useSettingsStore()
    await store.loadInterval()
    expect(store.pollIntervalMinutes).toBe(30)
  })

  it('saveInterval updates api and state', async () => {
    updateMock.mockResolvedValue({ data: { poll_interval_minutes: 15 } })
    const store = useSettingsStore()
    await store.saveInterval(15)
    expect(updateMock).toHaveBeenCalledWith(15)
    expect(store.pollIntervalMinutes).toBe(15)
  })
})

describe('settings 设备类型', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadTypes 拉取内置与自定义类型', async () => {
    fetchTypesMock.mockResolvedValue({ data: { builtin: ['group', 'camera'], custom: ['nas2'] } })
    const store = useSettingsStore()
    await store.loadTypes()
    expect(store.builtinTypes).toEqual(['group', 'camera'])
    expect(store.customTypes).toEqual(['nas2'])
    expect(store.typesLoaded).toBe(true)
  })

  it('addType 调用接口并刷新列表', async () => {
    addTypeMock.mockResolvedValue({ data: { ok: true } })
    fetchTypesMock.mockResolvedValue({ data: { builtin: ['group'], custom: ['nas2'] } })
    const store = useSettingsStore()
    await store.addType('nas2')
    expect(addTypeMock).toHaveBeenCalledWith('nas2')
    expect(store.customTypes).toContain('nas2')
  })

  it('removeType 调用接口并刷新列表', async () => {
    removeTypeMock.mockResolvedValue({ data: { ok: true } })
    fetchTypesMock.mockResolvedValue({ data: { builtin: ['group'], custom: [] } })
    const store = useSettingsStore()
    store.customTypes = ['nas2']
    await store.removeType('nas2')
    expect(removeTypeMock).toHaveBeenCalledWith('nas2')
    expect(store.customTypes).toEqual([])
  })
})

describe('settings ping 参数', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadPingParams 拉取当前 ping 参数', async () => {
    fetchPingMock.mockResolvedValue({ data: { ping_count: 5, ping_packet_size: 128 } })
    const store = useSettingsStore()
    await store.loadPingParams()
    expect(store.pingCount).toBe(5)
    expect(store.pingPacketSize).toBe(128)
  })

  it('savePingParams 调用接口并更新 state', async () => {
    updatePingMock.mockResolvedValue({ data: { ping_count: 8, ping_packet_size: 256 } })
    const store = useSettingsStore()
    await store.savePingParams(8, 256)
    expect(updatePingMock).toHaveBeenCalledWith(8, 256)
    expect(store.pingCount).toBe(8)
    expect(store.pingPacketSize).toBe(256)
  })
})