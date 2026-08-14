import { describe, it, expect, vi } from 'vitest'
import { downloadCsv, escapeCsvField, toCsv } from '../csv'

describe('toCsv', () => {
  it('输出带 BOM 的 CSV', () => {
    const out = toCsv(
      [{ name: 'A', ip: '1.1.1.1' }],
      [
        { key: 'name', header: '名称' },
        { key: 'ip', header: 'IP' },
      ]
    )
    expect(out.charCodeAt(0)).toBe(0xfeff)
    expect(out).toContain('名称,IP')
    expect(out).toContain('A,1.1.1.1')
  })

  it('逗号引号换行转义', () => {
    const out = toCsv(
      [{ v: 'a,b"c\nd' }],
      [{ key: 'v', header: 'V' }]
    )
    expect(out).toContain('"a,b""c')
  })

  it('空值填空白', () => {
    const out = toCsv([{ a: null, b: undefined }], [{ key: 'a', header: 'A' }, { key: 'b', header: 'B' }])
    expect(out).toContain(',')
  })
})

describe('escapeCsvField', () => {
  it('无特殊字符原样返回', () => {
    expect(escapeCsvField('abc')).toBe('abc')
  })
  it('含逗号加引号', () => {
    expect(escapeCsvField('a,b')).toBe('"a,b"')
  })
  it('含引号加倍', () => {
    expect(escapeCsvField('a"b')).toBe('"a""b"')
  })
})

describe('downloadCsv', () => {
  it('创建 Blob 并触发下载', () => {
    const create = vi.fn((blob) => 'blob:x')
    const revoke = vi.fn()
    const click = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    const anchor = { click, setAttribute: vi.fn(), style: {} }
    vi.stubGlobal('document', {
      createElement: () => anchor,
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
    })
    downloadCsv('a.csv', 'x')
    expect(create).toHaveBeenCalled()
    expect(click).toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})