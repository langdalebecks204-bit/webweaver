import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { recheckAllMock, loadMock } = vi.hoisted(() => ({
  recheckAllMock: vi.fn(),
  loadMock: vi.fn(),
}))

vi.mock('../../api/devices', () => ({
  createDevice: vi.fn(),
  deleteDevice: vi.fn(),
  fetchTree: vi.fn(),
  recheckAllDevices: recheckAllMock,
  recheckDevice: vi.fn(),
  updateDevice: vi.fn(),
}))

import { useDevicesStore } from '../devices'

describe('devices store recheckAll', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loadMock.mockResolvedValue(undefined)
  })

  it('calls recheck-all api then reloads tree', async () => {
    recheckAllMock.mockResolvedValue({})
    const store = useDevicesStore()
    store.load = loadMock
    await store.recheckAll()
    expect(recheckAllMock).toHaveBeenCalled()
    expect(loadMock).toHaveBeenCalledTimes(1)
  })
})
