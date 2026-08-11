// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { loginMock, fetchMeMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  fetchMeMock: vi.fn(),
}))

vi.mock('../../api/auth', () => ({
  login: loginMock,
  fetchMe: fetchMeMock,
}))

import { useAuthStore } from '../auth'

describe('auth store token storage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  it('stores token in localStorage by default (remember login)', async () => {
    loginMock.mockResolvedValue({ data: { access_token: 'abc' } })
    fetchMeMock.mockResolvedValue({ data: { username: 'admin', role: 'admin' } })
    const store = useAuthStore()
    await store.login('admin', 'pw', { rememberLogin: true })
    expect(localStorage.getItem('weaver_token')).toBe('abc')
    expect(sessionStorage.getItem('weaver_token')).toBeNull()
    expect(store.token).toBe('abc')
  })

  it('stores token in sessionStorage when not remembered', async () => {
    loginMock.mockResolvedValue({ data: { access_token: 'abc' } })
    fetchMeMock.mockResolvedValue({ data: { username: 'admin', role: 'admin' } })
    const store = useAuthStore()
    await store.login('admin', 'pw', { rememberLogin: false })
    expect(sessionStorage.getItem('weaver_token')).toBe('abc')
    expect(localStorage.getItem('weaver_token')).toBeNull()
    expect(store.token).toBe('abc')
  })

  it('reads persisted token from localStorage on init', () => {
    localStorage.setItem('weaver_token', 'persisted')
    const store = useAuthStore()
    expect(store.token).toBe('persisted')
  })

  it('reads persisted token from sessionStorage when local empty', () => {
    sessionStorage.setItem('weaver_token', 'session-token')
    const store = useAuthStore()
    expect(store.token).toBe('session-token')
  })

  it('logout clears both storages', () => {
    localStorage.setItem('weaver_token', 'a')
    sessionStorage.setItem('weaver_token', 'b')
    const store = useAuthStore()
    store.logout()
    expect(store.token).toBe('')
    expect(localStorage.getItem('weaver_token')).toBeNull()
    expect(sessionStorage.getItem('weaver_token')).toBeNull()
  })

  it('saves and loads remembered credentials', () => {
    const store = useAuthStore()
    store.saveCredentials('admin', 'secret123')
    expect(JSON.parse(localStorage.getItem('weaver_saved_credentials'))).toEqual({
      username: 'admin',
      password: 'secret123',
    })
  })

  it('clears remembered credentials', () => {
    const store = useAuthStore()
    store.saveCredentials('admin', 'secret123')
    store.clearCredentials()
    expect(localStorage.getItem('weaver_saved_credentials')).toBeNull()
  })
})