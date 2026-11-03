import { Tooltip } from './Primitives'

/**
 * Compact metric tile. `tone` follows the similarity palette so that a colour
 * always means the same thing across the product.
 */
export default function StatCard({
  label,
  value,
  suffix,
  hint,
  tooltip,
  tone = 'default',
  icon: Icon,
  footer,
}) {
  const tones = {
    default: { value: 'text-navy-900', chip: 'bg-navy-50 text-navy-500' },
    high: { value: 'text-red-700', chip: 'bg-red-50 text-red-600' },
    moderate: { value: 'text-amber-700', chip: 'bg-amber-50 text-amber-600' },
    low: { value: 'text-emerald-700', chip: 'bg-emerald-50 text-emerald-600' },
    accent: { value: 'text-accent-700', chip: 'bg-accent-50 text-accent-600' },
  }
  const style = tones[tone] || tones.default

  return (
    <div className="card flex flex-col justify-between p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <p className="label-micro">{label}</p>
          {tooltip && (
            <Tooltip text={tooltip}>
              <span className="flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full border border-navy-200 text-[9px] font-semibold text-navy-400">
                i
              </span>
            </Tooltip>
          )}
        </div>
        {Icon && (
          <span className={`flex h-7 w-7 items-center justify-center rounded-md ${style.chip}`}>
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
          </span>
        )}
      </div>
      <div className="mt-3">
        <p className={`tnum text-[26px] font-semibold leading-none tracking-[-0.02em] ${style.value}`}>
          {value}
          {suffix && <span className="ml-0.5 text-[15px] font-medium">{suffix}</span>}
        </p>
        {hint && <p className="mt-1.5 text-[11.5px] leading-snug text-navy-500">{hint}</p>}
      </div>
      {footer && <div className="mt-3 border-t border-navy-100 pt-2.5">{footer}</div>}
    </div>
  )
}
