import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDuration, number, pctValue } from '../utils/format'

const AXIS = { fontSize: 11, fill: '#5b7292' }

/**
 * Distribution of the best match score per comparable sentence in Document A.
 * Bars below the flag threshold stay visible so the shape of the comparison is
 * honest (a document can be 70% unrelated and still show one strong hit).
 */
export function SimilarityDistribution({ distribution = [], threshold = 0.62 }) {
  const data = distribution.map((bucket) => ({
    ...bucket,
    colour:
      bucket.lower >= 0.8 ? '#b91c1c' : bucket.lower >= 0.6 ? '#d97706' : bucket.lower >= 0.4 ? '#94a3b8' : '#cbd5e1',
    flagged: bucket.lower + 0.0001 >= threshold,
  }))

  return (
    <div className="h-[188px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -18 }} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke="#eef2f7" />
          <XAxis dataKey="range" tick={AXIS} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
          <YAxis
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
            width={44}
          />
          <RTooltip
            cursor={{ fill: 'rgba(37, 99, 235, 0.05)' }}
            contentStyle={{
              borderRadius: 8,
              border: '1px solid #e2e8f0',
              fontSize: 12,
              boxShadow: '0 6px 20px rgba(15,37,64,0.10)',
            }}
            formatter={(value) => [`${value} sentence(s)`, 'Count']}
            labelFormatter={(label) => `Best match similarity ${label}`}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]} maxBarSize={44}>
            {data.map((entry) => (
              <Cell key={entry.range} fill={entry.colour} fillOpacity={entry.flagged ? 1 : 0.55} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Compact horizontal coverage bars for both documents. */
export function CoveragePanel({ coverageA, coverageB, docs }) {
  const rows = [
    { key: 'A', label: 'Document A', data: coverageA, name: docs?.A?.filename },
    { key: 'B', label: 'Document B', data: coverageB, name: docs?.B?.filename },
  ]

  return (
    <div className="space-y-3.5">
      {rows.map((row) => {
        const sentencePct = row.data?.sentence_coverage_pct || 0
        const wordPct = row.data?.word_coverage_pct || 0
        return (
          <div key={row.key}>
            <div className="flex items-baseline justify-between gap-3">
              <div className="flex min-w-0 items-center gap-1.5">
                <span className="flex h-4 w-4 items-center justify-center rounded bg-navy-100 text-[9px] font-bold text-navy-600">
                  {row.key}
                </span>
                <span className="truncate text-[12px] font-medium text-navy-800" title={row.name}>
                  {row.name || row.label}
                </span>
              </div>
              <span className="tnum shrink-0 text-[12px] font-semibold text-navy-900">
                {pctValue(sentencePct)}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-navy-100">
              <div
                className="h-full rounded-full bg-accent-500"
                style={{ width: `${Math.min(100, sentencePct)}%` }}
                title={`${sentencePct}% of comparable sentences matched`}
              />
            </div>
            <p className="mt-1 text-[11px] text-navy-500">
              {number(row.data?.sentences_matched || 0)} of{' '}
              {number(row.data?.sentences_considered || 0)} comparable sentences ·{' '}
              {pctValue(wordPct)} of words covered
            </p>
          </div>
        )
      })}
    </div>
  )
}

/** Classification split as a single stacked bar + legend. */
export function ClassificationSplit({ summary }) {
  const parts = [
    { key: 'exact', label: 'Exact', value: summary.exact_matches, colour: '#b91c1c' },
    { key: 'near', label: 'Near-exact', value: summary.near_exact_matches, colour: '#d97706' },
    { key: 'semantic', label: 'Semantic', value: summary.semantic_matches, colour: '#2563eb' },
    { key: 'suppressed', label: 'Suppressed', value: summary.suppressed_matches, colour: '#94a3b8' },
  ]
  const total = parts.reduce((sum, part) => sum + (part.value || 0), 0) || 1

  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-navy-100">
        {parts.map((part) =>
          part.value ? (
            <div
              key={part.key}
              className="h-full"
              style={{ width: `${(part.value / total) * 100}%`, background: part.colour }}
              title={`${part.label}: ${part.value}`}
            />
          ) : null,
        )}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
        {parts.map((part) => (
          <li key={part.key} className="flex items-center gap-2">
            <span
              className="h-2 w-2 shrink-0 rounded-sm"
              style={{ background: part.colour }}
              aria-hidden="true"
            />
            <span className="flex-1 text-[11.5px] text-navy-600">{part.label}</span>
            <span className="tnum text-[12px] font-semibold text-navy-900">{part.value || 0}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Small sparkline-ish bar chart of recent analyses for the dashboard. */
export function ActivityChart({ data = [] }) {
  const chartData = data.map((row) => ({
    day: row.day?.slice(5) || '',
    analyses: row.analyses || 0,
    similarity: Math.round((row.avg_similarity || 0) * 100),
  }))

  if (chartData.length === 0) {
    return (
      <p className="py-8 text-center text-[12px] text-navy-400">
        No analyses yet — the chart fills in as you run comparisons.
      </p>
    )
  }

  return (
    <div className="h-[150px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 6, right: 4, bottom: 0, left: -24 }}>
          <CartesianGrid vertical={false} stroke="#eef2f7" />
          <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={38} />
          <RTooltip
            contentStyle={{
              borderRadius: 8,
              border: '1px solid #e2e8f0',
              fontSize: 12,
              boxShadow: '0 6px 20px rgba(15,37,64,0.10)',
            }}
            formatter={(value, key) =>
              key === 'analyses' ? [`${value}`, 'Analyses'] : [`${value}%`, 'Avg similarity']
            }
          />
          <Bar dataKey="analyses" fill="#2563eb" radius={[3, 3, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function DurationLabel({ ms }) {
  return <span className="tnum">{formatDuration(ms)}</span>
}
