import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const {
  fetchMock,
  createMock,
  updateMock,
  removeMock,
  checkAllMock,
  loadMock,
} = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  checkAllMock: vi.fn(),
  loadMock: vi.fn(),
}))

vi.mock('../../api/external', () => ({
  fetchExternalTargets: fetchMock,
  createExternalTarget: createMock,
  updateExternalTarget: updateMock,
  deleteExternalTarget: removeMock,
  checkAllExternalTargets: checkAllMock,
}))

import { useExternalStore } from '../external'

describe('external store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loadMock.mockResolvedValue(undefined)
  })

  it('load fetches targets', async () => {
    fetchMock.mockResolvedValue({ data: [{ id: 1, name: 't' }] })
    const store = useExternalStore()
    await store.load()
    expect(store.targets).toHaveLength(1)
  })

  it('create then reload', async () => {
    createMock.mockResolvedValue({ data: {} })
    const store = useExternalStore()
    store.load = loadMock
    await store.create({ name: 'x' })
    expect(createMock).toHaveBeenCalledWith({ name: 'x' })
    expect(loadMock).toHaveBeenCalledTimes(1)
  })

  it('checkAll then reload', async () => {
    checkAllMock.mockResolvedValue({})
    const store = useExternalStore()
    store.load = loadMock
    await store.checkAll()
    expect(checkAllMock).toHaveBeenCalled()
    expect(loadMock).toHaveBeenCalledTimes(1)
  })
})
