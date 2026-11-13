import { describe, it, expect } from 'vitest'
import {
  VISIO_SVG_PATHS,
  getVisioSvg,
  getVisioCanvasImage,
} from '../visioIcons'

describe('visioIcons utility', () => {
  const REQUIRED_TYPES = [
    'router',
    'switch',
    'unmanaged_switch',
    'firewall',
    'server',
    'ap',
    'terminal',
    'camera',
    'nvr',
    'printer',
    'nas',
    'ups',
    'group',
  ]

  it('provides valid SVG paths for all 13 built-in device types', () => {
    REQUIRED_TYPES.forEach((type) => {
      const svg = VISIO_SVG_PATHS[type]
      expect(svg, `Missing SVG for type: ${type}`).toBeDefined()
      expect(typeof svg).toBe('string')
      expect(svg).toContain('<svg')
      expect(svg).toContain('</svg>')
    })
  })

  it('getVisioSvg returns SVG for known types and fallback for unknown types', () => {
    const routerSvg = getVisioSvg('router')
    expect(routerSvg).toContain('<svg')
    expect(routerSvg).toContain('</svg>')

    const unknownSvg = getVisioSvg('some_custom_random_type')
    expect(unknownSvg).toBeDefined()
    expect(unknownSvg).toContain('<svg')
    expect(unknownSvg).toBe(getVisioSvg('default'))
  })

  it('getVisioCanvasImage returns cached HTMLImageElement or data url image', async () => {
    // In Node/happy-dom/jsdom environment
    const img = await getVisioCanvasImage('switch')
    expect(img).toBeDefined()
    if (typeof Image !== 'undefined') {
      expect(img).toBeInstanceOf(Image)
      expect(img.src).toContain('data:image/svg+xml')
    }
  })
})
