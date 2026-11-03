import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  Download,
  FilePlus2,
  History as HistoryIcon,
  Search,
  Trash2,
} from 'lucide-react'
import { useRequest } from '../hooks/useRequest'
import { deleteAnalysis, getHistory, reportUrl } from '../services/api'
import ConfirmDialog from '../components/ConfirmDialog'
import ScoreBar from '../components/ScoreBar'
import { Callout, EmptyState, Skeleton } from '../components/Primitives'
import { useToast } from '../components/Toast'
import { formatDateTime, formatDuration, number } from '../utils/format'
import { documentBandFromIndex } from '../utils/similarity'

const PAGE_SIZE = 12

export default function History() {
  const navigate = useNavigate()
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const { data, loading, error, reload } = useRequest(
    () => getHistory({ limit: PAGE_SIZE, offset: page * PAGE_SIZE, search: query }),
    [page, query],
  )

  const items = data?.items || []
  const total = data?.total || 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const handleSearch = (event) => {
    event.preventDefault()
    setPage(0)
    setQuery(search.trim())
  }

  const handleDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteAnalysis(pendingDelete.id)
      toast.success('Analysis deleted', { detail: 'Document text and match records removed.' })
      setPendingDelete(null)
      reload()
    } catch (err) {
      toast.error('Delete failed', { detail: err.message })
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1180px]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-[-0.02em] text-navy-900">Analysis history</h1>
          <p className="mt-0.5 text-[13px] text-navy-500">
            Every comparison stored in the database, with its measured metrics.
          </p>
        </div>
        <Link to="/analysis/new" className="btn btn-primary btn-md">
          <FilePlus2 className="h-3.5 w-3.5" aria-hidden="true" />
          New analysis
        </Link>
      </div>

      <div className="card mt-4 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-100 bg-navy-50/40 px-3.5 py-2.5">
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-navy-300" aria-hidden="true" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by document name"
                className="input h-8 w-56 pl-7 text-[12px]"
                aria-label="Search analyses by document name"
              />
            </div>
            <button type="submit" className="btn btn-ghost btn-sm">
              Search
            </button>
            {query && (
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => {
                  setSearch('')
                  setQuery('')
                  setPage(0)
                }}
              >
                Clear
              </button>
            )}
          </form>
          <p className="text-[11.5px] text-navy-500">
            {number(total)} analys{total === 1 ? 'is' : 'es'}
            {query ? ` matching “${query}”` : ''}
          </p>
        </div>

        {error && (
          <div className="p-4">
            <Callout tone="error" title="Could not load history">
              {error.message}{' '}
              <button type="button" className="link" onClick={reload}>
                Retry
              </button>
            </Callout>
          </div>
        )}

        {loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-12" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={HistoryIcon}
            title={query ? 'No analyses match that search' : 'No analyses yet'}
            description={
              query
                ? 'Try a different document name, or clear the search to see everything.'
                : 'Comparisons you run are stored here with their metrics, so you can revisit the evidence later.'
            }
            action={
              <Link to="/analysis/new" className="btn btn-primary btn-md">
                <FilePlus2 className="h-3.5 w-3.5" aria-hidden="true" />
                Run your first analysis
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse">
              <thead>
                <tr className="border-b border-navy-100 text-left">
                  {['Documents', 'Date', 'Similarity index', 'Matches', 'Coverage (A/B)', 'Duration', ''].map(
                    (label, index) => (
                      <th
                        key={label || index}
                        className="px-3 py-2 text-[10.5px] font-semibold uppercase tracking-[0.07em] text-navy-400 first:pl-4"
                      >
                        {label}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-navy-100 last:border-b-0 hover:bg-navy-50/40">
                    <td className="py-2.5 pl-4 pr-3">
                      <Link to={`/analysis/${item.id}`} className="group block">
                        <p className="truncate text-[12.5px] font-medium text-navy-900 group-hover:text-accent-700">
                          {item.doc_a_name}
                          <span className="mx-1.5 text-navy-300">↔</span>
                          {item.doc_b_name}
                        </p>
                        <p className="mt-0.5 font-mono text-[10.5px] text-navy-400">{item.id}</p>
                      </Link>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-[11.5px] text-navy-600">
                      {formatDateTime(item.created_at)}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="w-[120px]">
                        <ScoreBar
                          value={item.weighted_similarity}
                          size="sm"
                          band={documentBandFromIndex(item.weighted_similarity).meta}
                        />
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <p className="tnum text-[12px] font-medium text-navy-800">
                        {item.summary.primary_matches}
                      </p>
                      <p className="text-[10.5px] text-navy-400">
                        {item.summary.exact_matches}E · {item.summary.near_exact_matches}N ·{' '}
                        {item.summary.semantic_matches}S
                      </p>
                    </td>
                    <td className="px-3 py-2.5 text-[11.5px] text-navy-600">
                      <span className="tnum">{item.summary.coverage_a_pct}%</span>
                      <span className="mx-1 text-navy-300">/</span>
                      <span className="tnum">{item.summary.coverage_b_pct}%</span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-[11.5px] text-navy-500">
                      {formatDuration(item.duration_ms)}
                    </td>
                    <td className="py-2.5 pl-3 pr-4">
                      <div className="flex items-center justify-end gap-1">
                        <a
                          href={reportUrl(item.id)}
                          className="flex h-7 w-7 items-center justify-center rounded-md text-navy-400 hover:bg-white hover:text-navy-800"
                          title="Download PDF report"
                          download
                        >
                          <Download className="h-3.5 w-3.5" />
                        </a>
                        <button
                          type="button"
                          onClick={() => setPendingDelete(item)}
                          className="flex h-7 w-7 items-center justify-center rounded-md text-navy-400 hover:bg-red-50 hover:text-red-600"
                          title="Delete analysis"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => navigate(`/analysis/${item.id}`)}
                          className="flex h-7 w-7 items-center justify-center rounded-md text-navy-400 hover:bg-white hover:text-navy-800"
                          title="Open results"
                        >
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {pages > 1 && (
          <div className="flex items-center justify-between border-t border-navy-100 px-4 py-2.5">
            <p className="text-[11.5px] text-navy-500">
              Page {page + 1} of {pages}
            </p>
            <div className="flex gap-1.5">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setPage((value) => Math.max(0, value - 1))}
                disabled={page === 0}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setPage((value) => Math.min(pages - 1, value + 1))}
                disabled={page >= pages - 1}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete this analysis?"
        description={
          pendingDelete
            ? `${pendingDelete.doc_a_name} ↔ ${pendingDelete.doc_b_name}. The result, match records and any retained document text will be removed permanently.`
            : ''
        }
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}
