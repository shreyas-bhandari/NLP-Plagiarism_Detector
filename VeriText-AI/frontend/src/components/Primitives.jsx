import { AlertCircle, Info, Loader2, ShieldAlert, TriangleAlert } from 'lucide-react'

/* ------------------------------------------------------------------ spinner */
export function Spinner({ className = 'h-4 w-4', label = 'Loading' }) {
  return (
    <span role="status" aria-label={label}>
      <Loader2 className={`${className} animate-spin`} aria-hidden="true" />
    </span>
  )
}

export function Skeleton({ className = '' }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-navy-100/70 ${className}`}
      aria-hidden="true"
    />
  )
}

/* ------------------------------------------------------------------- callout */
const CALLOUT_STYLES = {
  info: {
    wrapper: 'border-accent-200 bg-accent-50/60',
    icon: 'text-accent-600',
    Icon: Info,
    title: 'text-accent-800',
    body: 'text-accent-900/80',
  },
  warning: {
    wrapper: 'border-amber-200 bg-amber-50/70',
    icon: 'text-amber-600',
    Icon: TriangleAlert,
    title: 'text-amber-900',
    body: 'text-amber-900/80',
  },
  disclaimer: {
    wrapper: 'border-navy-200 bg-navy-50',
    icon: 'text-navy-500',
    Icon: ShieldAlert,
    title: 'text-navy-800',
    body: 'text-navy-600',
  },
  error: {
    wrapper: 'border-red-200 bg-red-50',
    icon: 'text-red-600',
    Icon: AlertCircle,
    title: 'text-red-800',
    body: 'text-red-700',
  },
}

export function Callout({ tone = 'info', title, children, className = '', action }) {
  const style = CALLOUT_STYLES[tone] || CALLOUT_STYLES.info
  const { Icon } = style
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-3.5 py-3 ${style.wrapper} ${className}`}>
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${style.icon}`} aria-hidden="true" />
      <div className="min-w-0 flex-1 text-[12.5px] leading-relaxed">
        {title && <p className={`mb-0.5 text-[12.5px] font-semibold ${style.title}`}>{title}</p>}
        <div className={style.body}>{children}</div>
      </div>
      {action}
    </div>
  )
}

/* ---------------------------------------------------------------- empty state */
export function EmptyState({ icon: Icon, title, description, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center px-6 py-14 text-center ${className}`}>
      {Icon && (
        <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-navy-50 text-navy-400">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
      )}
      <p className="text-[14px] font-semibold text-navy-800">{title}</p>
      {description && (
        <p className="mt-1 max-w-md text-[12.5px] leading-relaxed text-navy-500">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/* --------------------------------------------------------------------- misc */
export function SectionTitle({ children, hint, action }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4">
      <div>
        <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-navy-900">{children}</h2>
        {hint && <p className="mt-0.5 text-[12.5px] text-navy-500">{hint}</p>}
      </div>
      {action}
    </div>
  )
}

export function KeyValue({ label, value, mono = false }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="text-[12.5px] text-navy-500">{label}</dt>
      <dd className={`text-[12.5px] font-medium text-navy-900 ${mono ? 'font-mono' : ''}`}>
        {value}
      </dd>
    </div>
  )
}

export function Tooltip({ text, children }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 w-56 -translate-x-1/2
                   rounded-md bg-navy-900 px-2.5 py-1.5 text-[11px] font-normal leading-snug text-white
                   opacity-0 shadow-pop transition-opacity duration-150 group-hover:opacity-100"
      >
        {text}
      </span>
    </span>
  )
}
