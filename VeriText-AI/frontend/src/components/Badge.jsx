import { AlertTriangle, Equal, GitCompareArrows, MinusCircle } from 'lucide-react'
import { classificationMeta, strengthMeta, BAND_META } from '../utils/similarity'

const base =
  'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-semibold leading-[1.4]'

const ICONS = {
  exact: Equal,
  near_exact: GitCompareArrows,
  semantic: MinusCircle,
}

export function ClassificationBadge({ classification, compact = false, showIcon = true }) {
  const meta = classificationMeta(classification)
  const Icon = ICONS[classification]
  return (
    <span className={`${base} ${meta.bg} ${meta.border} ${meta.text}`}>
      {showIcon && Icon ? <Icon className="h-3 w-3" aria-hidden="true" /> : null}
      {compact ? meta.short : meta.label}
    </span>
  )
}

export function StrengthBadge({ strength }) {
  const meta = strengthMeta(strength)
  return <span className={`${base} ${meta.className}`}>{meta.label}</span>
}

export function BandBadge({ band }) {
  const meta = BAND_META[band] || BAND_META.low
  return (
    <span className={`${base} ${meta.bg} ${meta.border} ${meta.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} aria-hidden="true" />
      {meta.label}
    </span>
  )
}

export function SuppressedBadge({ reason, label }) {
  return (
    <span className={`${base} border-navy-200 bg-navy-50 text-navy-500`} title={reason || ''}>
      <AlertTriangle className="h-3 w-3" aria-hidden="true" />
      {label || 'Suppressed'}
    </span>
  )
}

export function CountPill({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'bg-navy-50 text-navy-600 border-navy-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    accent: 'bg-accent-50 text-accent-700 border-accent-200',
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  }
  return <span className={`${base} ${tones[tone]}`}>{children}</span>
}
