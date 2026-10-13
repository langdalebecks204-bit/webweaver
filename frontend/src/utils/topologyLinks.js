export const SPEED_COLORS = {
  offline: '#ef4444',
  10000: '#3b82f6',
  2500: '#39ff14',
  1000: '#10b981',
  100: '#f97316',
  unknown: '#94a3b8',
}

export function getLinkColor(link, snmpSpeedMap = new Map()) {
  const sStatus = typeof link.source === 'object' ? link.source.status : null
  const tStatus = typeof link.target === 'object' ? link.target.status : null
  if (link.status === 'offline' || sStatus === 'offline' || tStatus === 'offline') {
    return SPEED_COLORS.offline
  }

  const sId = typeof link.source === 'object' ? link.source.id : link.source
  const tId = typeof link.target === 'object' ? link.target.id : link.target

  const snmpKey1 = `${sId}->${tId}`
  const snmpKey2 = `${tId}->${sId}`
  let speed = snmpSpeedMap.get(snmpKey1) ?? snmpSpeedMap.get(snmpKey2)

  if (!speed) {
    if (typeof link.source === 'object' && link.source.port_bindings) {
      for (const b of Object.values(link.source.port_bindings)) {
        if (b.target_id === tId && b.speed_mbps) {
          speed = b.speed_mbps
          break
        }
      }
    }
    if (!speed && typeof link.target === 'object' && link.target.port_bindings) {
      for (const b of Object.values(link.target.port_bindings)) {
        if (b.target_id === sId && b.speed_mbps) {
          speed = b.speed_mbps
          break
        }
      }
    }
  }

  if (link.speed_mbps) {
    speed = link.speed_mbps
  }

  if (speed >= 10000) return SPEED_COLORS[10000]
  if (speed >= 2500) return SPEED_COLORS[2500]
  if (speed >= 1000) return SPEED_COLORS[1000]
  if (speed >= 100) return SPEED_COLORS[100]
  return SPEED_COLORS.unknown
}
