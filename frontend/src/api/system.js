import client from './client'

export function checkUpdate(mirror = '') {
  return client.get('/system/update/check', { params: { mirror } })
}

export function applyUpdate(downloadUrl, mirror = '') {
  return client.post('/system/update/apply', {
    download_url: downloadUrl,
    mirror,
  })
}

export function healthCheck() {
  return client.get('/health', { timeout: 1500 })
}
