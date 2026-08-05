import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { fetchMock, updateMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('../../api/settings', () => ({
  fetchInspectionInterval: fetchMock,
  updateInspectionInterval: updateMock,
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
