const intFormatter = new Intl.NumberFormat('en-IN')

export function fmtInt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return intFormatter.format(value)
}

export function fmtPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return `${Math.round(value * 100)}%`
}

export function fmtBytes(bytes) {
  if (!bytes) return ''
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function activityLevelClass(level) {
  switch (level) {
    case 'LOW':
      return 'level level--low'
    case 'MODERATE':
      return 'level level--moderate'
    case 'HIGH':
      return 'level level--high'
    default:
      return 'level level--none'
  }
}
