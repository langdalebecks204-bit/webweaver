import JSZip from 'jszip'
import { toCsv } from './csv'

const ILLEGAL = /[\\/:*?"<>|]/g

export function imageFileName(row) {
  return `${String(row.name).replace(ILLEGAL, '_')}_${row.id}.jpg`
}

export function statusClass(status) {
  if (status === 'online') return 'st-online'
  if (status === 'offline') return 'st-offline'
  if (status === 'warning') return 'st-warning'
  return 'st-unknown'
}

function statusText(s) {
  return s === 'online' ? '在线' : s === 'offline' ? '离线' : s === 'warning' ? '警告' : '未知'
}

export function buildDeviceHtml({ rows, columns }) {
  const headers = columns.map((c) => `<th>${c.header}</th>`).join('')
  const body = rows
    .map((row) => {
      const tds = columns
        .map((c) => {
          let val = c.format ? c.format(row[c.key]) : row[c.key]
          if (val === null || val === undefined) val = ''
          if (c.key === 'status') {
            return `<td class="${statusClass(row.status)}">${statusText(row.status)}</td>`
          }
          if (c.key === 'image_file') {
            return val
              ? `<td><img src="images/${val}" loading="lazy"></td>`
              : '<td>-</td>'
          }
          return `<td>${String(val).replace(/</g, '&lt;')}</td>`
        })
        .join('')
      return `<tr>${tds}</tr>`
    })
    .join('')
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>设备资产</title>
<style>
  body { font-family: 'Microsoft YaHei', sans-serif; margin: 24px; color: #333; }
  h1 { font-size: 20px; }
  table { border-collapse: collapse; width: 100%; margin-top: 16px; }
  th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; }
  th { background: #f5f7fa; }
  img { width: 90px; height: 60px; object-fit: cover; border-radius: 4px; }
  .st-online { color: #67c23a; font-weight: 600; }
  .st-offline { color: #f56c6c; font-weight: 600; }
  .st-warning { color: #e6a23c; font-weight: 600; }
  .st-unknown { color: #909399; }
</style>
</head>
<body>
<h1>设备资产</h1>
<p>导出时间：${new Date().toLocaleString()}</p>
<table>${headers ? `<thead><tr>${headers}</tr></thead>` : ''}<tbody>${body}</tbody></table>
</body>
</html>`
}

async function fetchImageBlob(row) {
  const res = await fetch(row.image_url)
  if (!res.ok) throw new Error(`fetch failed: ${row.image_url}`)
  return res.blob()
}

export async function buildExportZip({
  rows,
  csvColumns,
  htmlColumns = csvColumns,
  fetchImage = fetchImageBlob,
}) {
  const zip = new JSZip()
  const withImage = rows.map((row) => {
    const file = row.image_url ? imageFileName(row) : ''
    return { ...row, image_file: file }
  })
  await Promise.all(
    withImage.map(async (row) => {
      if (!row.image_file) return
      try {
        const blob = await fetchImage(row)
        zip.file(`images/${row.image_file}`, new Uint8Array(await blob.arrayBuffer()))
      } catch {
        row.image_file = ''
      }
    })
  )
  zip.file('设备资产.csv', toCsv(withImage, csvColumns))
  zip.file('设备资产.html', buildDeviceHtml({ rows: withImage, columns: htmlColumns }))
  return zip.generateAsync({ type: 'blob' })
}