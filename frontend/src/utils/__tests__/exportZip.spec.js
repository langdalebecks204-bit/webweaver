import { describe, it, expect, vi } from 'vitest'
import JSZip from 'jszip'
import { buildDeviceHtml, buildExportZip } from '../exportZip'

const rows = [
  {
    id: 12,
    name: '核心交换机',
    type: 'switch',
    ip_address: '10.0.0.1',
    image_url: '/uploads/12.jpg',
  },
  { id: 13, name: '终端B', type: 'terminal', ip_address: '10.0.0.2', image_url: null },
]

const columns = [
  { key: 'name', header: '名称' },
  { key: 'ip_address', header: 'IP' },
  { key: 'image_file', header: '图片' },
]

async function readZip(blob) {
  return JSZip.loadAsync(await blob.arrayBuffer())
}

describe('buildExportZip', () => {
  it('打包 CSV 与图片，命名正确，无图设备图片列留空', async () => {
    const fetchImage = vi.fn(async () => new Blob(['jpg-bytes-12'], { type: 'image/jpeg' }))
    const blob = await buildExportZip({ rows, csvColumns: columns, fetchImage })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).toContain('设备资产.csv')
    expect(Object.keys(zip.files)).toContain('images/核心交换机_12.jpg')
    expect(Object.keys(zip.files)).not.toContain('images/终端B_13.jpg')
    const csv = await zip.file('设备资产.csv').async('string')
    expect(csv).toContain('核心交换机,10.0.0.1,核心交换机_12.jpg')
    expect(csv).toContain('终端B,10.0.0.2,')
    const img = await zip.file('images/核心交换机_12.jpg').async('arraybuffer')
    expect(new TextDecoder().decode(img)).toBe('jpg-bytes-12')
    expect(fetchImage).toHaveBeenCalledTimes(1)
  })

  it('图片 fetch 失败时跳过该图且 CSV 留空，不抛异常', async () => {
    const fetchImage = vi.fn(async () => { throw new Error('network') })
    const blob = await buildExportZip({ rows, csvColumns: columns, fetchImage })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).not.toContain('images/核心交换机_12.jpg')
    const csv = await zip.file('设备资产.csv').async('string')
    expect(csv).toContain('核心交换机,10.0.0.1,')
  })

  it('图片文件名中的非法字符替换为下划线', async () => {
    const weird = [{ id: 1, name: 'A/B:C*D', image_url: '/uploads/1.jpg' }]
    const fetchImage = vi.fn(async () => new Blob(['x']))
    const blob = await buildExportZip({ rows: weird, csvColumns: columns, fetchImage })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).toContain('images/A_B_C_D_1.jpg')
  })
})

const htmlColumns = [
  { key: 'name', header: '名称' },
  { key: 'ip_address', header: 'IP' },
  { key: 'status', header: '状态' },
  { key: 'image_file', header: '图片' },
]

const htmlRows = [
  {
    id: 12, name: '核心交换机', type: 'switch', ip_address: '10.0.0.1',
    status: 'online', latency_ms: 5, last_check: '2026-08-14T02:30:00+00:00',
    image_file: '核心交换机_12.jpg',
  },
  {
    id: 13, name: '终端B', type: 'terminal', ip_address: '10.0.0.2',
    status: 'offline', latency_ms: null, last_check: null, image_file: '',
  },
]

describe('buildDeviceHtml', () => {
  it('生成含表格、缩略图与中文状态文本的 HTML', () => {
    const html = buildDeviceHtml({ rows: htmlRows, columns: htmlColumns })
    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<table>')
    expect(html).toContain('核心交换机')
    expect(html).toContain('在线')
    expect(html).toContain('<img src="images/核心交换机_12.jpg"')
    expect(html).toContain('st-online')
    expect(html).not.toContain('<img src="images/终端B_13.jpg"')
  })

  it('无图设备图片列显示 - 且不含 img', () => {
    const html = buildDeviceHtml({ rows: htmlRows.slice(1), columns: htmlColumns })
    expect(html).not.toContain('<img')
    expect(html).toContain('终端B')
  })

  it('含标题', () => {
    const html = buildDeviceHtml({ rows: [], columns: htmlColumns })
    expect(html).toContain('<h1>')
  })
})

describe('buildExportZip csv+html', () => {
  it('ZIP 同时含 csv 与 html 文件', async () => {
    const fetchImage = vi.fn(async () => new Blob(['jpg']))
    const blob = await buildExportZip({
      rows,
      csvColumns: [...columns, { key: 'image_file', header: '图片' }],
      fetchImage,
    })
    const zip = await readZip(blob)
    expect(Object.keys(zip.files)).toContain('设备资产.csv')
    expect(Object.keys(zip.files)).toContain('设备资产.html')
    const html = await zip.file('设备资产.html').async('string')
    expect(html).toContain('<table>')
  })
})
