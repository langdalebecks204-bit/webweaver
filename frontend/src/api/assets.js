import client from './client'

export default {
  getAssets(targetDeviceId = null) {
    const params = targetDeviceId ? { target_device_id: targetDeviceId } : {}
    return client.get('/assets', { params })
  },
  scanAssets(targetDeviceId = null) {
    const params = targetDeviceId ? { target_device_id: targetDeviceId } : {}
    return client.post('/assets/scan', null, { params })
  },
  enrollAsset(payload) {
    return client.post('/assets/enroll', payload)
  },
}
