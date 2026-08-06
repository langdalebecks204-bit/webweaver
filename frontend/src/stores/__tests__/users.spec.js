import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { fetchMock, createMock, updateMock, removeMock, loadMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  loadMock: vi.fn(),
}))

vi.mock('../../api/users', () => ({
  fetchUsers: fetchMock,
  createUser: createMock,
  updateUser: updateMock,
  deleteUser: removeMock,
}))

import { useUsersStore } from '../users'

describe('users store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loadMock.mockResolvedValue(undefined)
  })

  it('load fetches users', async () => {
    fetchMock.mockResolvedValue({ data: [{ id: 1, username: 'admin' }] })
    const store = useUsersStore()
    await store.load()
    expect(store.users).toHaveLength(1)
  })

  it('create then reload', async () => {
    createMock.mockResolvedValue({ data: {} })
    const store = useUsersStore()
    store.load = loadMock
    await store.create({ username: 'x', password: 'pw123456', role: 'viewer' })
    expect(createMock).toHaveBeenCalledWith({ username: 'x', password: 'pw123456', role: 'viewer' })
    expect(loadMock).toHaveBeenCalledTimes(1)
  })

  it('remove then reload', async () => {
    removeMock.mockResolvedValue({})
    const store = useUsersStore()
    store.load = loadMock
    await store.remove(2)
    expect(removeMock).toHaveBeenCalledWith(2)
    expect(loadMock).toHaveBeenCalledTimes(1)
  })
})