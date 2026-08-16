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

export function fetchPingParams() {
  return client.get('/settings/ping-params')
}

export function updatePingParams(count, size) {
  return client.put('/settings/ping-params', { ping_count: count, ping_packet_size: size })
}
