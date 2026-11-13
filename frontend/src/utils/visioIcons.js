/**
 * Visio / Cisco Classic Network Vector SVG Icons
 * Provides clean, sharp, self-contained SVG strings and pre-rendered Canvas Images.
 */

export const VISIO_SVG_PATHS = {
  // 1. Router: Classic Cisco 3D Blue Cylinder with 4 crossing arrows
  router: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <ellipse cx="24" cy="14" rx="20" ry="8" fill="#0284c7" stroke="#0369a1" stroke-width="1.5" />
    <path d="M4 14 v16 c0 4.4 8.95 8 20 8 s20 -3.6 20 -8 V14" fill="#0369a1" stroke="#075985" stroke-width="1.5" />
    <ellipse cx="24" cy="30" rx="20" ry="8" fill="none" stroke="#38bdf8" stroke-width="1" stroke-dasharray="2 2" />
    <!-- 4 Arrows on top ellipse -->
    <path d="M12 14 h8 M18 11 l3 3 -3 3" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M36 14 h-8 M30 11 l-3 3 3 3" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M24 8 v4 M21 10 l3 3 3 -3" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M24 20 v-4 M21 18 l3 -3 3 3" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>`,

  // 2. Switch (Managed L2/L3): Classic Cisco 3D Blue Box with 4 opposing arrows
  switch: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <!-- Top Face -->
    <polygon points="10,12 38,12 44,18 16,18" fill="#38bdf8" stroke="#0284c7" stroke-width="1.2" />
    <!-- Front Face -->
    <rect x="10" y="18" width="28" height="18" rx="2" fill="#0284c7" stroke="#0369a1" stroke-width="1.2" />
    <!-- Right Face -->
    <polygon points="38,18 44,18 44,36 38,36" fill="#0369a1" stroke="#075985" stroke-width="1.2" />
    <!-- 4 Opposing Arrows -->
    <path d="M15 23 h16 M28 20 l4 3 -4 3" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" />
    <path d="M33 30 h-16 M20 27 l-4 3 4 3" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" />
    <!-- Mini Port LEDs -->
    <circle cx="14" cy="33" r="1.2" fill="#4ade80" />
    <circle cx="18" cy="33" r="1.2" fill="#4ade80" />
    <circle cx="22" cy="33" r="1.2" fill="#4ade80" />
  </svg>`,

  // 3. Unmanaged Switch / Hub: Compact gray/slate desktop box with port grid
  unmanaged_switch: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <rect x="6" y="15" width="36" height="20" rx="3" fill="#64748b" stroke="#334155" stroke-width="1.5" />
    <rect x="10" y="18" width="28" height="8" rx="1.5" fill="#1e293b" />
    <!-- Hub ports -->
    <rect x="12" y="20" width="3" height="4" fill="#94a3b8" />
    <rect x="17" y="20" width="3" height="4" fill="#94a3b8" />
    <rect x="22" y="20" width="3" height="4" fill="#94a3b8" />
    <rect x="27" y="20" width="3" height="4" fill="#94a3b8" />
    <rect x="32" y="20" width="3" height="4" fill="#94a3b8" />
    <!-- Indicator LEDs -->
    <circle cx="13.5" cy="29" r="1" fill="#22c55e" />
    <circle cx="18.5" cy="29" r="1" fill="#22c55e" />
    <circle cx="23.5" cy="29" r="1" fill="#eab308" />
    <circle cx="28.5" cy="29" r="1" fill="#22c55e" />
    <circle cx="33.5" cy="29" r="1" fill="#22c55e" />
  </svg>`,

  // 4. Firewall: Classic Brick Wall with Security Shield/Lock
  firewall: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <rect x="6" y="10" width="36" height="28" rx="2" fill="#dc2626" stroke="#991b1b" stroke-width="1.5" />
    <!-- Brick mortar lines -->
    <line x1="6" y1="17" x2="42" y2="17" stroke="#ffffff" stroke-width="1" />
    <line x1="6" y1="24" x2="42" y2="24" stroke="#ffffff" stroke-width="1" />
    <line x1="6" y1="31" x2="42" y2="31" stroke="#ffffff" stroke-width="1" />
    <line x1="18" y1="10" x2="18" y2="17" stroke="#ffffff" stroke-width="1" />
    <line x1="30" y1="10" x2="30" y2="17" stroke="#ffffff" stroke-width="1" />
    <line x1="12" y1="17" x2="12" y2="24" stroke="#ffffff" stroke-width="1" />
    <line x1="24" y1="17" x2="24" y2="24" stroke="#ffffff" stroke-width="1" />
    <line x1="36" y1="17" x2="36" y2="24" stroke="#ffffff" stroke-width="1" />
    <line x1="18" y1="24" x2="18" y2="31" stroke="#ffffff" stroke-width="1" />
    <line x1="30" y1="24" x2="30" y2="31" stroke="#ffffff" stroke-width="1" />
    <!-- Center yellow security lock badge -->
    <rect x="20" y="20" width="8" height="7" rx="1.5" fill="#facc15" stroke="#ca8a04" stroke-width="0.8" />
    <path d="M22 20 v-3 a2 2 0 0 1 4 0 v3" fill="none" stroke="#facc15" stroke-width="1.2" />
  </svg>`,

  // 5. Server: Classic 2U/4U Rack Server with Drive Bays
  server: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <rect x="8" y="9" width="32" height="13" rx="1.5" fill="#334155" stroke="#1e293b" stroke-width="1.2" />
    <line x1="12" y1="13" x2="26" y2="13" stroke="#94a3b8" stroke-width="1.5" />
    <line x1="12" y1="17" x2="26" y2="17" stroke="#94a3b8" stroke-width="1.5" />
    <circle cx="34" cy="15.5" r="1.5" fill="#22c55e" />
    <circle cx="30" cy="15.5" r="1.5" fill="#38bdf8" />

    <rect x="8" y="25" width="32" height="13" rx="1.5" fill="#334155" stroke="#1e293b" stroke-width="1.2" />
    <line x1="12" y1="29" x2="26" y2="29" stroke="#94a3b8" stroke-width="1.5" />
    <line x1="12" y1="33" x2="26" y2="33" stroke="#94a3b8" stroke-width="1.5" />
    <circle cx="34" cy="31.5" r="1.5" fill="#22c55e" />
    <circle cx="30" cy="31.5" r="1.5" fill="#38bdf8" />
  </svg>`,

  // 6. Wireless AP: Classic Saucer AP with Radio Waves
  ap: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <!-- AP Body -->
    <ellipse cx="24" cy="27" rx="15" ry="7" fill="#0284c7" stroke="#0369a1" stroke-width="1.2" />
    <circle cx="24" cy="26" r="2.5" fill="#38bdf8" />
    <!-- Radio Waves -->
    <path d="M16 18 a11 6 0 0 1 16 0" fill="none" stroke="#0284c7" stroke-width="1.6" stroke-linecap="round" />
    <path d="M11 12 a18 10 0 0 1 26 0" fill="none" stroke="#0ea5e9" stroke-width="1.6" stroke-linecap="round" />
    <path d="M6 7 a25 14 0 0 1 36 0" fill="none" stroke="#38bdf8" stroke-width="1.6" stroke-linecap="round" />
  </svg>`,

  // 7. Terminal / PC: Monitor + Stand + Host
  terminal: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <!-- Monitor -->
    <rect x="8" y="10" width="24" height="18" rx="2" fill="#0f172a" stroke="#475569" stroke-width="1.2" />
    <rect x="10" y="12" width="20" height="14" fill="#38bdf8" />
    <!-- Stand -->
    <path d="M20 28 v4 M16 32 h8" fill="none" stroke="#475569" stroke-width="1.5" stroke-linecap="round" />
    <!-- Mini Tower -->
    <rect x="34" y="12" width="8" height="20" rx="1.5" fill="#334155" stroke="#1e293b" stroke-width="1.2" />
    <line x1="36" y1="16" x2="40" y2="16" stroke="#94a3b8" stroke-width="1" />
    <circle cx="38" cy="28" r="1" fill="#22c55e" />
  </svg>`,

  // 8. Camera: Classic Security Dome / Bullet Cam
  camera: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <path d="M8 12 h16 l6 6 v14 h-22 z" fill="#475569" stroke="#1e293b" stroke-width="1.2" />
    <polygon points="30,18 42,12 42,32 30,26" fill="#0284c7" stroke="#0369a1" stroke-width="1.2" />
    <circle cx="18" cy="23" r="5" fill="#0f172a" stroke="#38bdf8" stroke-width="1.2" />
    <circle cx="18" cy="23" r="2" fill="#ef4444" />
  </svg>`,

  // 9. NVR: Video Recorder Unit
  nvr: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <rect x="6" y="16" width="36" height="18" rx="2" fill="#1e293b" stroke="#475569" stroke-width="1.5" />
    <circle cx="15" cy="25" r="4" fill="none" stroke="#38bdf8" stroke-width="1.5" />
    <circle cx="23" cy="25" r="4" fill="none" stroke="#38bdf8" stroke-width="1.5" />
    <line x1="15" y1="21" x2="23" y2="21" stroke="#38bdf8" stroke-width="1.2" />
    <rect x="31" y="21" width="7" height="8" rx="1" fill="#dc2626" />
  </svg>`,

  // 10. Printer: Office Network Laser Printer
  printer: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <!-- Paper in top -->
    <rect x="15" y="8" width="18" height="10" fill="#f8fafc" stroke="#94a3b8" stroke-width="1" />
    <!-- Body -->
    <rect x="8" y="16" width="32" height="18" rx="3" fill="#475569" stroke="#1e293b" stroke-width="1.2" />
    <!-- Output paper -->
    <rect x="13" y="24" width="22" height="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
    <circle cx="34" cy="20" r="1.5" fill="#22c55e" />
  </svg>`,

  // 11. NAS: Storage Appliance Enclosure
  nas: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <rect x="12" y="8" width="24" height="32" rx="3" fill="#334155" stroke="#1e293b" stroke-width="1.5" />
    <!-- Drive bays -->
    <rect x="16" y="12" width="16" height="5" rx="1" fill="#475569" stroke="#94a3b8" stroke-width="0.8" />
    <rect x="16" y="19" width="16" height="5" rx="1" fill="#475569" stroke="#94a3b8" stroke-width="0.8" />
    <rect x="16" y="26" width="16" height="5" rx="1" fill="#475569" stroke="#94a3b8" stroke-width="0.8" />
    <!-- Activity LEDs -->
    <circle cx="28" cy="34" r="1.2" fill="#22c55e" />
    <circle cx="24" cy="34" r="1.2" fill="#38bdf8" />
  </svg>`,

  // 12. UPS: Battery Power Unit with Lightning Bolt
  ups: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <rect x="13" y="10" width="22" height="30" rx="3" fill="#0f172a" stroke="#334155" stroke-width="1.5" />
    <!-- Terminals on top -->
    <rect x="17" y="7" width="4" height="3" fill="#ef4444" />
    <rect x="27" y="7" width="4" height="3" fill="#3b82f6" />
    <!-- Lightning bolt -->
    <polygon points="25,16 19,26 23,26 21,34 29,23 25,23" fill="#eab308" stroke="#ca8a04" stroke-width="0.8" />
  </svg>`,

  // 13. Group: Logical Network Cloud
  group: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <path d="M14 34 a9 9 0 0 1 -2 -17 a13 13 0 0 1 24 -3 a10 10 0 0 1 4 19 z" 
          fill="#f1f5f9" stroke="#64748b" stroke-width="1.8" stroke-dasharray="3 2" />
  </svg>`,

  // Default fallback
  default: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
    <rect x="10" y="12" width="28" height="24" rx="3" fill="#64748b" stroke="#334155" stroke-width="1.5" />
    <circle cx="24" cy="24" r="5" fill="#38bdf8" />
  </svg>`,
}

/**
 * Returns clean SVG string for a given device type, fallback to default.
 */
export function getVisioSvg(type) {
  if (type && VISIO_SVG_PATHS[type]) {
    return VISIO_SVG_PATHS[type]
  }
  return VISIO_SVG_PATHS.default
}

// In-memory Canvas Image cache for 60fps rendering in ForceGraph / Canvas 2D
const canvasImageCache = new Map()

/**
 * Get or create an HTMLImageElement preloaded with the SVG DataURL.
 */
export function getVisioCanvasImage(type) {
  const safeType = type && VISIO_SVG_PATHS[type] ? type : 'default'
  if (canvasImageCache.has(safeType)) {
    return canvasImageCache.get(safeType)
  }

  const svgStr = getVisioSvg(safeType)
  const encoded = encodeURIComponent(svgStr)
  const dataUrl = `data:image/svg+xml;charset=utf-8,${encoded}`

  if (typeof Image !== 'undefined') {
    const img = new Image()
    img.src = dataUrl
    canvasImageCache.set(safeType, img)
    return img
  }

  return { src: dataUrl }
}

/**
 * Preloads all built-in images so Canvas drawImage does not flicker on first render.
 */
export function preloadAllVisioCanvasImages() {
  if (typeof Image === 'undefined') return
  Object.keys(VISIO_SVG_PATHS).forEach((type) => {
    getVisioCanvasImage(type)
  })
}
