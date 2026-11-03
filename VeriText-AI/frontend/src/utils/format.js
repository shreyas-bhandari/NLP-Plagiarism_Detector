/** Formatting helpers shared across pages. */

export const pct = (value, digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export const pctValue = (value, digits = 1) =>
  value === null || value === undefined ? '—' : `${Number(value).toFixed(digits)}%`

export const number = (value) => {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('en-US').format(value)
}

export const parseDate = (iso) => {
  if (!iso) return null
  try {
    const date = new Date(iso)
    return Number.isNaN(date.getTime()) ? null : date
  } catch {
    return null
  }
}

export const formatDate = (iso) => {
  const date = parseDate(iso)
  if (!date) return '—'
  return date.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

export const formatDateTime = (iso) => {
  const date = parseDate(iso)
  if (!date) return '—'
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const relativeTime = (iso) => {
  const date = parseDate(iso)
  if (!date) return '—'
  const diff = Date.now() - date.getTime()
  const minutes = Math.round(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} d ago`
  return formatDate(iso)
}

export const formatDuration = (ms) => {
  if (!ms && ms !== 0) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

export const formatBytes = (bytes) => {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const truncate = (text, max = 160) => {
  if (!text) return ''
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`
}

export const pluralise = (count, singular, plural) =>
  `${number(count)} ${count === 1 ? singular : plural || `${singular}s`}`
