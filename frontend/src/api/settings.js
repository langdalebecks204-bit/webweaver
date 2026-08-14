import client from './client'

export function fetchInspectionInterval() {
  return client.get('/settings/inspection-interval')
}

export function updateInspectionInterval(minutes) {
  return client.put('/settings/inspection-interval', { poll_interval_minutes: minutes })
}

export function fetchDeviceTypes() {
  return client.get('/settings/device-types')
}

export function addDeviceType(name) {
  return client.post('/settings/device-types', { name })
}

export function removeDeviceType(name) {
  return client.delete(`/settings/device-types/${encodeURIComponent(name)}`)
}
