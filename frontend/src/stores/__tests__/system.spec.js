// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSystemStore } from '../system'
import * as systemApi from '../../api/system'

vi.mock('../../api/system')

describe('SystemStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('checkUpdate updates state correctly', async () => {
    systemApi.checkUpdate.mockResolvedValue({
      data: {
        current_version: '0.5.4',
        latest_version: '0.5.5',
        has_update: true,
        release_notes: 'new features',
        published_at: '2026-09-20T10:00:00Z',
        download_url: 'http://test/tar.gz',
        size: 2048,
      },
    })
    const store = useSystemStore()
    await store.check()
    expect(store.currentVersion).toBe('0.5.4')
    expect(store.latestVersion).toBe('0.5.5')
    expect(store.hasUpdate).toBe(true)
    expect(store.releaseNotes).toBe('new features')
    expect(store.downloadUrl).toBe('http://test/tar.gz')
    expect(store.packageSize).toBe(2048)
  })

  it('apply calls api with download_url and mirror', async () => {
    systemApi.applyUpdate.mockResolvedValue({
      data: { status: 'success', message: 'restarting' },
    })
    const store = useSystemStore()
    store.downloadUrl = 'http://test/tar.gz'
    store.selectedMirror = 'https://ghproxy.net/'
    const res = await store.apply()
    expect(systemApi.applyUpdate).toHaveBeenCalledWith(
      'http://test/tar.gz',
      'https://ghproxy.net/'
    )
    expect(res.data.status).toBe('success')
  })

  it('waitForHealth succeeds when healthCheck returns 200', async () => {
    systemApi.healthCheck.mockResolvedValue({ status: 200 })
    const store = useSystemStore()
    const ok = await store.waitForHealth(3, 10)
    expect(ok).toBe(true)
  })
})
