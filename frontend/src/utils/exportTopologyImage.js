import { getVisioCanvasImage } from './visioIcons'

export function calculateGraphBounds(nodes, padding = 80) {
  if (!nodes || nodes.length === 0) {
    return { minX: -400, maxX: 400, minY: -300, maxY: 300, width: 800, height: 600 }
  }

  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity

  for (const n of nodes) {
    const x = n.x ?? n.fx ?? 0
    const y = n.y ?? n.fy ?? 0
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }

  const pMinX = Math.round(minX - padding)
  const pMaxX = Math.round(maxX + padding)
  const pMinY = Math.round(minY - padding)
  const pMaxY = Math.round(maxY + padding)

  return {
    minX: pMinX,
    maxX: pMaxX,
    minY: pMinY,
    maxY: pMaxY,
    width: Math.max(200, pMaxX - pMinX),
    height: Math.max(200, pMaxY - pMinY),
  }
}

export async function exportFullTopologyImage(nodes, links, options = {}) {
  if (!nodes || nodes.length === 0) return false
  if (typeof document === 'undefined') return false

  const scale = options.scale || 2
  const bounds = calculateGraphBounds(nodes, options.padding || 90)

  const canvas = document.createElement('canvas')
  canvas.width = bounds.width * scale
  canvas.height = bounds.height * scale
  const ctx = canvas.getContext('2d')
  if (!ctx) return false

  ctx.scale(scale, scale)
  ctx.translate(-bounds.minX, -bounds.minY)

  // 1. Background
  ctx.fillStyle = options.background || '#ffffff'
  ctx.fillRect(bounds.minX, bounds.minY, bounds.width, bounds.height)

  // 2. Subtle grid lines
  const gridSize = 30
  ctx.save()
  ctx.strokeStyle = '#f1f5f9'
  ctx.lineWidth = 1
  const startX = Math.floor(bounds.minX / gridSize) * gridSize
  const endX = Math.ceil(bounds.maxX / gridSize) * gridSize
  const startY = Math.floor(bounds.minY / gridSize) * gridSize
  const endY = Math.ceil(bounds.maxY / gridSize) * gridSize

  ctx.beginPath()
  for (let x = startX; x <= endX; x += gridSize) {
    ctx.moveTo(x, bounds.minY)
    ctx.lineTo(x, bounds.maxY)
  }
  for (let y = startY; y <= endY; y += gridSize) {
    ctx.moveTo(bounds.minX, y)
    ctx.lineTo(bounds.maxX, y)
  }
  ctx.stroke()
  ctx.restore()

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  function getNodePos(endpoint) {
    if (typeof endpoint === 'object' && endpoint !== null) {
      return { x: endpoint.x ?? endpoint.fx ?? 0, y: endpoint.y ?? endpoint.fy ?? 0 }
    }
    const n = nodeMap.get(endpoint)
    return { x: n?.x ?? n?.fx ?? 0, y: n?.y ?? n?.fy ?? 0 }
  }

  // 3. Links & Port Labels
  ctx.save()
  for (const l of links || []) {
    const s = getNodePos(l.source)
    const t = getNodePos(l.target)

    ctx.strokeStyle = l.status === 'offline' ? '#ef4444' : '#94a3b8'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.moveTo(s.x, s.y)
    ctx.lineTo(t.x, t.y)
    ctx.stroke()

    // Port labels
    const sPort = l.source_port
    const tPort = l.target_port
    ctx.font = '9px monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'

    if (sPort) {
      const px = s.x + (t.x - s.x) * 0.22
      const py = s.y + (t.y - s.y) * 0.22
      const tw = ctx.measureText(sPort).width
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(px - tw / 2 - 3, py - 6, tw + 6, 12)
      ctx.strokeStyle = '#cbd5e1'
      ctx.lineWidth = 0.8
      ctx.strokeRect(px - tw / 2 - 3, py - 6, tw + 6, 12)
      ctx.fillStyle = '#475569'
      ctx.fillText(sPort, px, py)
    }

    if (tPort) {
      const px = s.x + (t.x - s.x) * 0.78
      const py = s.y + (t.y - s.y) * 0.78
      const tw = ctx.measureText(tPort).width
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(px - tw / 2 - 3, py - 6, tw + 6, 12)
      ctx.strokeStyle = '#cbd5e1'
      ctx.lineWidth = 0.8
      ctx.strokeRect(px - tw / 2 - 3, py - 6, tw + 6, 12)
      ctx.fillStyle = '#475569'
      ctx.fillText(tPort, px, py)
    }
  }
  ctx.restore()

  // 4. Nodes
  const STATUS_COLORS = {
    online: '#10b981',
    warning: '#f59e0b',
    offline: '#ef4444',
    unknown: '#94a3b8',
  }

  for (const n of nodes) {
    const nx = n.x ?? n.fx ?? 0
    const ny = n.y ?? n.fy ?? 0
    const iconSize = 46
    const half = iconSize / 2

    const img = getVisioCanvasImage(n.type)
    if (img && img.src) {
      try {
        ctx.drawImage(img, nx - half, ny - half, iconSize, iconSize)
      } catch (e) {
        ctx.fillStyle = '#64748b'
        ctx.fillRect(nx - half, ny - half, iconSize, iconSize)
      }
    } else {
      ctx.fillStyle = '#64748b'
      ctx.fillRect(nx - half, ny - half, iconSize, iconSize)
    }

    // Top-right LED indicator
    const ledX = nx + half - 4
    const ledY = ny - half + 4
    const color = STATUS_COLORS[n.status] || '#94a3b8'
    ctx.save()
    ctx.beginPath()
    ctx.arc(ledX, ledY, 4.5, 0, 2 * Math.PI)
    ctx.fillStyle = color
    ctx.fill()
    ctx.lineWidth = 1.2
    ctx.strokeStyle = '#ffffff'
    ctx.stroke()
    ctx.restore()

    // Text labels
    ctx.save()
    ctx.font = 'bold 11px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#1e293b'
    ctx.fillText(n.name, nx, ny + half + 4)

    if (n.ip_address) {
      ctx.font = '9px monospace'
      ctx.fillStyle = '#64748b'
      ctx.fillText(n.ip_address, nx, ny + half + 18)
    }
    ctx.restore()
  }

  // 5. Trigger download
  const now = new Date()
  const pad = (num) => String(num).padStart(2, '0')
  const dateStr = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  const filename = options.filename || `WebWeaver_Topology_Visio_${dateStr}.png`

  try {
    const dataUrl = canvas.toDataURL('image/png')
    const link = document.createElement('a')
    link.download = filename
    link.href = dataUrl
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    return true
  } catch (err) {
    console.error('Failed to export topology canvas image', err)
    return false
  }
}
