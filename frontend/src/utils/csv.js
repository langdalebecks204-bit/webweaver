export function escapeCsvField(value) {
  if (value === null || value === undefined) return ''
  const s = String(value)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

export function toCsv(rows, columns) {
  const header = columns.map((c) => escapeCsvField(c.header)).join(',')
  const lines = rows.map((row) =>
    columns.map((c) => escapeCsvField(c.format ? c.format(row[c.key]) : row[c.key])).join(',')
  )
  return '\uFEFF' + [header, ...lines].join('\r\n')
}

export function downloadCsv(filename, content) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}