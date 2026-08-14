import JSZip from 'jszip'
import { toCsv } from './csv'

const ILLEGAL = /[\\/:*?"<>|]/g

export function imageFileName(row) {
  return `${String(row.name).replace(ILLEGAL, '_')}_${row.id}.jpg`
}

async function fetchImageBlob(row) {
  const res = await fetch(row.image_url)
  if (!res.ok) throw new Error(`fetch failed: ${row.image_url}`)
  return res.blob()
}

export async function buildExportZip({ rows, csvColumns, fetchImage = fetchImageBlob }) {
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
  return zip.generateAsync({ type: 'blob' })
}