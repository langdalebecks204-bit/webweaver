import client from './client'

export function fetchTree() {
  return client.get('/devices/tree')
}

export function fetchDevices(params) {
  return client.get('/devices', { params })
}

export function createDevice(payload) {
  return client.post('/devices', payload)
}

export function updateDevice(id, payload) {
  return client.put(`/devices/${id}`, payload)
}

export function deleteDevice(id) {
  return client.delete(`/devices/${id}`)
}

export function recheckDevice(id) {
  return client.post(`/devices/${id}/recheck`)
}

export function recheckAllDevices() {
  return client.post('/devices/recheck-all')
}

export function fetchDeviceHistory(id, days) {
  return client.get(`/devices/${id}/history`, { params: { days } })
}

export function uploadDeviceImage(id, file) {
  const form = new FormData()
  form.append('file', file)
  return client.post(`/devices/${id}/image`, form)
}

export function deleteDeviceImage(id) {
  return client.delete(`/devices/${id}/image`)
}

export function getDeviceSnmpInterfaces(id) {
  return client.get(`/devices/${id}/snmp/interfaces`)
}

