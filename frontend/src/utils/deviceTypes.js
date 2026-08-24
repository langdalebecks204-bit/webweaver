export const DEVICE_TYPE_LABELS = {
  group: '分组',
  server: '服务器',
  switch: '交换机',
  terminal: '终端',
  camera: '摄像头',
  nvr: 'NVR',
  router: '路由器',
  firewall: '防火墙',
  ap: '无线AP',
  printer: '打印机',
  nas: 'NAS',
  ups: 'UPS',
  unmanaged_switch: '非管理型交换机',
}

export const DEVICE_TYPE_ICONS = {
  group: 'Folder',
  server: 'Monitor',
  switch: 'Connection',
  terminal: 'Cpu',
  camera: 'VideoCamera',
  nvr: 'Film',
  router: 'Position',
  firewall: 'Lock',
  ap: 'Cellphone',
  printer: 'Printer',
  nas: 'Files',
  ups: 'Lightning',
  unmanaged_switch: 'Connection',
}

export const DEFAULT_TYPE_ICON = 'Monitor'
export const UNKNOWN_TYPE_ICON = 'QuestionFilled'

export const DEVICE_TYPE_GLYPHS = {
  group: '📁',
  server: '🖥️',
  switch: '🔀',
  terminal: '💻',
  camera: '📷',
  nvr: '🎛️',
  router: '📡',
  firewall: '🛡️',
  ap: '📶',
  printer: '🖨️',
  nas: '💾',
  ups: '🔋',
  unmanaged_switch: '🔌',
}

export function typeGlyph(type) {
  if (DEVICE_TYPE_GLYPHS[type]) return DEVICE_TYPE_GLYPHS[type]
  if (type) return typeLabel(type)[0] || '?'
  return '?'
}

export function typeLabel(type) {
  return DEVICE_TYPE_LABELS[type] || type
}

export function typeIcon(type, customTypes = []) {
  if (!type) return UNKNOWN_TYPE_ICON
  if (DEVICE_TYPE_ICONS[type]) return DEVICE_TYPE_ICONS[type]
  if (customTypes.includes(type)) return DEFAULT_TYPE_ICON
  return UNKNOWN_TYPE_ICON
}

export function allTypeOptions(builtinTypes, customTypes) {
  const opts = builtinTypes.map((t) => ({ value: t, label: DEVICE_TYPE_LABELS[t] || t }))
  for (const t of customTypes) {
    if (!DEVICE_TYPE_LABELS[t]) opts.push({ value: t, label: t })
  }
  return opts
}