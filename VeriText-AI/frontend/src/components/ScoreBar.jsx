import { bandMeta } from '../utils/similarity'

/**
 * Similarity meter. Width encodes the cosine score; colour encodes the band.
 * The numeric value is always shown as text so the bar is never the only signal
 * (accessibility + honest reporting).
 */
export default function ScoreBar({ value, showValue = true, size = 'md', band, className = '' }) {
  const percent = Math.max(0, Math.min(100, (value || 0) * 100))
  const meta = bandMeta(band)
  const height = size === 'sm' ? 'h-1.5' : 'h-2'

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className={`relative ${height} flex-1 overflow-hidden rounded-full bg-navy-100`}
        role="meter"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Semantic similarity"
      >
        <div
          className={`h-full rounded-full ${meta.bar} transition-[width] duration-300`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {showValue && (
        <span className={`tnum w-11 shrink-0 text-right text-[12px] font-semibold ${meta.text}`}>
          {percent.toFixed(1)}
          <span className="text-[10px] font-medium">%</span>
        </span>
      )}
    </div>
  )
}
