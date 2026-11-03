import { Link } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Clock3,
  FilePlus2,
  Files,
  GitCompareArrows,
  ScanSearch,
  Timer,
} from 'lucide-react'
import { useRequest } from '../hooks/useRequest'
import { getDashboardStats, getHistory } from '../services/api'
import StatCard from '../components/StatCard'
import ScoreBar from '../components/ScoreBar'
import { ActivityChart } from '../components/charts'
import { Callout, EmptyState, Skeleton } from '../components/Primitives'
import { formatDateTime, formatDuration, number, relativeTime } from '../utils/format'
import { documentBandFromIndex } from '../utils/similarity'

function StatusPill({ status }) {
  if (status === 'failed') {
    return (
      <span className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[11px] font-medium text-red-700">
        Failed
      </span>
    )
  }
  return (
    <span className="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700">
      Completed
    </span>
  )
}

function RecentRow({ item }) {
  const band = documentBandFromIndex(item.weighted_similarity)
  return (
    <tr className="group border-b border-navy-100 last:border-b-0 hover:bg-navy-50/40">
      <td className="py-2.5 pl-4 pr-3">
        <Link to={`/analysis/${item.id}`} className="block min-w-0">
          <p className="truncate text-[12.5px] font-medium text-navy-900">
            {item.doc_a_name}
            <span className="mx-1.5 text-navy-300">↔</span>
            {item.doc_b_name}
          </p>
          <p className="mt-0.5 text-[11px] text-navy-400">
            {formatDateTime(item.created_at)} · {number(item.doc_a_words + item.doc_b_words)} words
          </p>
        </Link>
      </td>
      <td className="px-3 py-2.5">
        <div className="w-[132px]">
          <ScoreBar value={item.weighted_similarity} band={band.meta} size="sm" />
        </div>
      </td>
      <td className="px-3 py-2.5">
        <span className="tnum text-[12.5px] font-medium text-navy-800">{item.primary_matches}</span>
        <span className="ml-1 text-[11px] text-navy-400">matches</span>
      </td>
      <td className="px-3 py-2.5">
        <StatusPill status={item.status} />
      </td>
      <td className="py-2.5 pl-3 pr-4 text-right">
        <span className="tnum whitespace-nowrap text-[11.5px] text-navy-400">
          {formatDuration(item.duration_ms)}
        </span>
        <Link
          to={`/analysis/${item.id}`}
          className="ml-2 inline-flex h-7 w-7 items-center justify-center rounded-md text-navy-400 hover:bg-white hover:text-navy-800"
          aria-label={`Open analysis of ${item.doc_a_name} and ${item.doc_b_name}`}
        >
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </td>
    </tr>
  )
}

export default function Dashboard() {
  const stats = useRequest(() => getDashboardStats(), [])
  const history = useRequest(() => getHistory({ limit: 6 }), [])

  const isLoading = stats.loading || history.loading
  const error = stats.error || history.error
  const data = stats.data
  const recent = history.data?.items || []
  const hasAnalyses = (data?.total_analyses || 0) > 0

  return (
    <div className="mx-auto max-w-[1180px]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-[-0.02em] text-navy-900">Dashboard</h1>
          <p className="mt-0.5 text-[13px] text-navy-500">
            Workspace overview — every figure is read from the analysis database.
          </p>
        </div>
        <Link to="/analysis/new" className="btn btn-primary btn-md">
          <FilePlus2 className="h-3.5 w-3.5" aria-hidden="true" />
          New comparison
        </Link>
      </div>

      {error && (
        <div className="mt-4">
          <Callout tone="error" title="Could not load workspace data">
            {error.message} {error.hint}
            <button type="button" className="link ml-2" onClick={() => { stats.reload(); history.reload() }}>
              Try again
            </button>
          </Callout>
        </div>
      )}

      {/* ------------------------------------------------------------- stats */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-[116px]" />)
        ) : (
          <>
            <StatCard
              label="Total analyses"
              value={number(data?.total_analyses || 0)}
              icon={Activity}
              tone="accent"
              hint={`${number(data?.completed_analyses || 0)} completed · ${number(data?.failed_analyses || 0)} failed`}
            />
            <StatCard
              label="Documents processed"
              value={number(data?.documents_processed || 0)}
              icon={Files}
              hint="Two documents per comparison"
            />
            <StatCard
              label="Average analysis time"
              value={data?.average_duration_ms ? formatDuration(data.average_duration_ms) : '—'}
              icon={Timer}
              hint="End-to-end, including embedding"
            />
            <StatCard
              label="Avg similarity index"
              value={hasAnalyses ? (data?.average_weighted_similarity_pct ?? 0).toFixed(1) : '—'}
              suffix={hasAnalyses ? '%' : ''}
              icon={GitCompareArrows}
              tone={
                !hasAnalyses
                  ? 'default'
                  : data.average_weighted_similarity_pct >= 45
                    ? 'high'
                    : data.average_weighted_similarity_pct >= 25
                      ? 'moderate'
                      : 'low'
              }
              hint="Across completed comparisons"
              tooltip="Mean of the coverage-weighted similarity index of all completed analyses. Not a plagiarism percentage."
            />
          </>
        )}
      </div>

      <div className="mt-4 grid items-start gap-3 lg:grid-cols-[1.55fr_1fr]">
        {/* --------------------------------------------------- recent table */}
        <div className="card overflow-hidden">
          <div className="card-header">
            <div>
              <p className="text-[13px] font-semibold text-navy-900">Recent comparisons</p>
              <p className="mt-0.5 text-[11.5px] text-navy-500">Latest six analyses from the database</p>
            </div>
            <Link to="/history" className="btn btn-ghost btn-sm">
              All history
              <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>

          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-10" />
              ))}
            </div>
          ) : recent.length === 0 ? (
            <EmptyState
              icon={ScanSearch}
              title="No analyses yet"
              description="Run your first comparison to populate the dashboard. Metrics, charts and history all appear here once real analyses exist."
              action={
                <Link to="/analysis/new" className="btn btn-primary btn-md">
                  <FilePlus2 className="h-3.5 w-3.5" aria-hidden="true" />
                  New analysis
                </Link>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse">
                <thead>
                  <tr className="border-b border-navy-100 bg-navy-50/40 text-left">
                    {['Documents', 'Similarity index', 'Matches', 'Status', 'Time'].map((label) => (
                      <th
                        key={label}
                        className="px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.07em] text-navy-400 first:pl-4"
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recent.map((item) => (
                    <RecentRow key={item.id} item={item} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="border-t border-navy-100 p-3">
            <Callout tone="disclaimer" title="How to read these numbers">
              The similarity index combines how much of a document matched with how closely it
              matched. It is a triage signal for review, not a measure of misconduct, and it only
              reflects the two documents you supplied.
            </Callout>
          </div>
        </div>

        {/* ------------------------------------------------------- right rail */}
        <div className="space-y-3">
          <div className="card p-4">
            <div className="flex items-center justify-between">
              <p className="text-[13px] font-semibold text-navy-900">Analysis activity</p>
              <Clock3 className="h-3.5 w-3.5 text-navy-300" aria-hidden="true" />
            </div>
            <p className="mt-0.5 text-[11.5px] text-navy-500">Analyses per day, last 14 days</p>
            <div className="mt-2">
              <ActivityChart data={data?.activity || []} />
            </div>
          </div>

          <div className="card p-4">
            <p className="text-[13px] font-semibold text-navy-900">Quick comparison</p>
            <p className="mt-0.5 text-[11.5px] leading-relaxed text-navy-500">
              Upload a submission and a source document to start a semantic comparison.
            </p>
            <Link to="/analysis/new" className="btn btn-primary btn-md mt-3 w-full">
              <FilePlus2 className="h-3.5 w-3.5" aria-hidden="true" />
              Upload documents
            </Link>

            <dl className="mt-4 space-y-2 border-t border-navy-100 pt-3">
              {[
                { label: 'Exact matches found', value: number(data?.total_exact_matches || 0) },
                { label: 'Near-exact matches', value: number(data?.total_near_exact_matches || 0) },
                { label: 'Semantic matches', value: number(data?.total_semantic_matches || 0) },
              ].map((row) => (
                <div key={row.label} className="flex items-baseline justify-between">
                  <dt className="text-[11.5px] text-navy-500">{row.label}</dt>
                  <dd className="tnum text-[12px] font-semibold text-navy-900">{row.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {recent[0] && (
            <div className="card p-4">
              <p className="label-micro">Latest activity</p>
              <p className="mt-1.5 text-[12.5px] font-medium text-navy-900">
                {recent[0].doc_a_name} ↔ {recent[0].doc_b_name}
              </p>
              <p className="mt-0.5 text-[11.5px] text-navy-500">
                {relativeTime(recent[0].created_at)} · {recent[0].primary_matches} matches ·{' '}
                {(recent[0].weighted_similarity * 100).toFixed(1)}% index
              </p>
              <Link to={`/analysis/${recent[0].id}`} className="link mt-2 inline-flex items-center gap-1 text-[12px]">
                Open result
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
          )}
        </div>
      </div>

      <div className="mt-3">
        <Callout tone="disclaimer" title="How to read these numbers">
          The similarity index combines how much of a document matched with how closely it matched. It
          is a triage signal for review, not a measure of misconduct, and it only reflects the two
          documents you supplied.
        </Callout>
      </div>
    </div>
  )
}
