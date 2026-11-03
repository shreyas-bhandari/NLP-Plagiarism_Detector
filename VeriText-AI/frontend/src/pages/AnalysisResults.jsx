import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  Columns2,
  Download,
  FileJson,
  Filter,
  Gauge,
  Hash,
  Layers,
  Percent,
  Search,
  ShieldAlert,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useRequest } from '../hooks/useRequest'
import { deleteAnalysis, exportUrl, getAnalysis, reportUrl } from '../services/api'
import StatCard from '../components/StatCard'
import MatchItem from '../components/MatchItem'
import ConfirmDialog from '../components/ConfirmDialog'
import { BandBadge } from '../components/Badge'
import { ClassificationSplit, CoveragePanel, SimilarityDistribution } from '../components/charts'
import { Callout, EmptyState, SectionTitle, Skeleton, Tooltip } from '../components/Primitives'
import { useToast } from '../components/Toast'
import { formatDateTime, formatDuration, number, pctValue } from '../utils/format'
import { documentBandMeta } from '../utils/similarity'

const FILTERS = [
  { key: 'all', label: 'All matches' },
  { key: 'exact', label: 'Exact' },
  { key: 'near_exact', label: 'Near-exact' },
  { key: 'semantic', label: 'Semantic' },
  { key: 'suppressed', label: 'Suppressed' },
]

export default function AnalysisResults() {
  const { analysisId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { data, loading, error, reload } = useRequest(() => getAnalysis(analysisId), [analysisId])

  const [filter, setFilter] = useState('all')
  const [includeAlternatives, setIncludeAlternatives] = useState(false)
  const [showParagraphs, setShowParagraphs] = useState(false)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('similarity')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const result = data && data.status === 'completed' ? data : null
  const summary = result?.summary
  const band = summary ? documentBandMeta(summary.band?.level) : null

  const matches = useMemo(() => {
    if (!result) return []
    let list = result.matches.filter((match) => (includeAlternatives ? true : match.is_primary))
    if (filter === 'suppressed') {
      list = list.filter((match) => match.suppressed)
    } else if (filter !== 'all') {
      list = list.filter((match) => match.classification === filter && !match.suppressed)
    }
    if (search.trim()) {
      const needle = search.trim().toLowerCase()
      list = list.filter(
        (match) =>
          match.source.text.toLowerCase().includes(needle) ||
          match.target.text.toLowerCase().includes(needle),
      )
    }
    if (sort === 'similarity') {
      list = [...list].sort((a, b) => b.similarity - a.similarity)
    } else if (sort === 'source') {
      list = [...list].sort((a, b) => a.source.index - b.source.index)
    }
    return list
  }, [result, filter, includeAlternatives, search, sort])

  const paragraphMatches = useMemo(
    () =>
      [...(result?.paragraph_matches || [])].sort((a, b) => b.similarity - a.similarity),
    [result],
  )

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteAnalysis(analysisId)
      toast.success('Analysis deleted', { detail: 'Stored document text and results removed.' })
      navigate('/history')
    } catch (err) {
      toast.error('Could not delete analysis', { detail: err.message })
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  /* --------------------------------------------------------------- states */
  if (loading) {
    return (
      <div className="mx-auto max-w-[1180px] space-y-3">
        <Skeleton className="h-8 w-72" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-[116px]" />
          ))}
        </div>
        <Skeleton className="h-64" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (error) {
    const expired = error.status === 404
    return (
      <div className="mx-auto max-w-2xl">
        <div className="card p-6">
          <EmptyState
            icon={AlertTriangle}
            title={expired ? 'Analysis not found' : 'Could not load this analysis'}
            description={
              expired
                ? 'It may have been deleted, or the identifier is incorrect.'
                : `${error.message} ${error.hint || ''}`
            }
            action={
              <div className="flex gap-2">
                <Link to="/history" className="btn btn-ghost btn-md">
                  Back to history
                </Link>
                <Link to="/analysis/new" className="btn btn-primary btn-md">
                  New analysis
                </Link>
              </div>
            }
          />
        </div>
      </div>
    )
  }

  if (data && data.status === 'failed') {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="card p-6">
          <Callout tone="error" title="This analysis failed">
            {data.error_message || 'The engine could not complete the comparison.'}
          </Callout>
          <div className="mt-4 flex gap-2">
            <Link to="/analysis/new" className="btn btn-primary btn-md">
              Try again
            </Link>
            <Link to="/history" className="btn btn-ghost btn-md">
              Back to history
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (!result) return null

  const docs = result.documents
  const engine = result.engine
  const thresholds = engine.thresholds

  return (
    <div className="mx-auto max-w-[1180px]">
      {/* ---------------------------------------------------------- header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to="/history"
            className="inline-flex items-center gap-1 text-[11.5px] font-medium text-navy-400 hover:text-navy-700"
          >
            <ArrowLeft className="h-3 w-3" aria-hidden="true" />
            Analysis history
          </Link>
          <h1 className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[19px] font-semibold tracking-[-0.02em] text-navy-900">
            <span className="truncate">{docs.A.filename}</span>
            <span className="text-navy-300">↔</span>
            <span className="truncate">{docs.B.filename}</span>
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11.5px] text-navy-500">
            <span>{formatDateTime(result.created_at)}</span>
            <span className="text-navy-200">·</span>
            <span className="font-mono">{result.analysis_id}</span>
            <span className="text-navy-200">·</span>
            <span>engine {engine.version}</span>
            <span className="text-navy-200">·</span>
            <span title="Device the embeddings were computed on in this run">
              {engine.device === 'cuda' ? 'GPU' : engine.device === 'mps' ? 'MPS' : 'CPU'} inference
            </span>
            <span className="text-navy-200">·</span>
            <span>{formatDuration(engine.timings.total_ms)} total</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <a href={reportUrl(analysisId)} className="btn btn-primary btn-md" download>
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
            PDF report
          </a>
          <a href={exportUrl(analysisId)} className="btn btn-ghost btn-md" download>
            <FileJson className="h-3.5 w-3.5" aria-hidden="true" />
            JSON
          </a>
          {result.session_text_available ? (
            <Link to={`/analysis/${analysisId}/viewer`} className="btn btn-ghost btn-md">
              <Columns2 className="h-3.5 w-3.5" aria-hidden="true" />
              Side-by-side
            </Link>
          ) : (
            <Tooltip text={`Document text is retained for ${result.retention_minutes} minutes for privacy. Scores and snippets remain available.`}>
              <span className="btn btn-ghost btn-md cursor-not-allowed opacity-50">
                <Columns2 className="h-3.5 w-3.5" aria-hidden="true" />
                Side-by-side
              </span>
            </Tooltip>
          )}
          <button
            type="button"
            className="btn btn-danger btn-md"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            Delete
          </button>
        </div>
      </div>

      {/* -------------------------------------------------------- disclaimer */}
      <div className="mt-4">
        <Callout tone="disclaimer" title="Read this before interpreting any score">
          {result.disclaimer}
        </Callout>
      </div>

      {/* ----------------------------------------------------------- metrics */}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Similarity index"
          value={summary.weighted_similarity_pct.toFixed(1)}
          suffix="%"
          tone={band.bar?.includes('red') ? 'high' : band.bar?.includes('amber') ? 'moderate' : 'low'}
          icon={Gauge}
          hint={summary.band?.label}
          tooltip={summary.explanation_of_weighted_index}
          footer={
            <p className="text-[11px] leading-snug text-navy-500">
              Highest single sentence: <span className="tnum font-semibold text-navy-800">{pctValue(summary.max_similarity_pct)}</span>
            </p>
          }
        />
        <StatCard
          label="Matched sentences (A)"
          value={summary.coverage.A.sentence_coverage_pct.toFixed(1)}
          suffix="%"
          icon={Percent}
          hint={`${number(summary.coverage.A.sentences_matched)} of ${number(summary.coverage.A.sentences_considered)} comparable sentences`}
          footer={
            <p className="text-[11px] leading-snug text-navy-500">
              Words covered: <span className="tnum font-semibold text-navy-800">{pctValue(summary.coverage.A.word_coverage_pct)}</span>
            </p>
          }
        />
        <StatCard
          label="Primary matches"
          value={number(summary.primary_matches)}
          icon={Hash}
          hint={`${number(summary.evidence_rows ?? summary.primary_matches)} evidence rows · ${number(
            summary.all_match_candidates,
          )} candidates evaluated`}
          footer={
            <p className="flex flex-wrap gap-1.5 text-[10.5px] font-medium">
              <span className="rounded bg-red-50 px-1.5 py-0.5 text-red-700">{summary.exact_matches} exact</span>
              <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-700">{summary.near_exact_matches} near</span>
              <span className="rounded bg-accent-50 px-1.5 py-0.5 text-accent-700">{summary.semantic_matches} semantic</span>
            </p>
          }
        />
        <StatCard
          label="Avg. matched similarity"
          value={summary.average_matched_similarity_pct.toFixed(1)}
          suffix="%"
          tone="accent"
          icon={Sparkles}
          hint={`${number(summary.passages_detected)} passage(s) detected`}
          footer={
            <p className="text-[11px] leading-snug text-navy-500">
              Suppressed as noise: <span className="tnum font-semibold text-navy-800">{summary.suppressed_matches}</span>
              {' · '}generic: <span className="tnum font-semibold text-navy-800">{summary.generic_phrasing_matches || 0}</span>
            </p>
          }
        />
      </div>

      {/* ------------------------------------------------------------ panels */}
      <div className="mt-3 grid gap-3 lg:grid-cols-[1.5fr_1fr]">
        <div className="card">
          <div className="card-header">
            <div>
              <p className="text-[13px] font-semibold text-navy-900">Similarity distribution</p>
              <p className="mt-0.5 text-[11.5px] text-navy-500">
                Best match cosine per comparable sentence in {docs.A.filename}
              </p>
            </div>
            <span className="rounded border border-navy-200 px-1.5 py-0.5 text-[10.5px] font-medium text-navy-500">
              flag ≥ {thresholds.semantic_min.toFixed(2)}
            </span>
          </div>
          <div className="px-2 pb-2 pt-3">
            <SimilarityDistribution distribution={summary.distribution} threshold={thresholds.semantic_min} />
          </div>
          <p className="border-t border-navy-100 px-4 py-2.5 text-[11px] leading-snug text-navy-500">
            Sentences below the threshold are shown too: the shape matters more than a single average.
            Coverage-weighted index = Σ(best cosine of each matched sentence in A, counted once) ÷
            comparable sentences in A — always between 0% and 100%.
          </p>
        </div>

        <div className="space-y-3">
          <div className="card p-4">
            <p className="text-[13px] font-semibold text-navy-900">Match classification</p>
            <p className="mt-0.5 text-[11.5px] text-navy-500">Different evidence types, counted separately</p>
            <div className="mt-3">
              <ClassificationSplit summary={summary} />
            </div>
          </div>
          <div className="card p-4">
            <p className="text-[13px] font-semibold text-navy-900">Matched coverage</p>
            <p className="mt-0.5 text-[11.5px] text-navy-500">How much of each document has a qualifying match</p>
            <div className="mt-3">
              <CoveragePanel coverageA={summary.coverage.A} coverageB={summary.coverage.B} docs={docs} />
            </div>
          </div>
        </div>
      </div>

      {/* ---------------------------------------------------------- passages */}
      {(result.passages || []).length > 0 && (
        <div className="mt-3">
          <SectionTitle
            hint="Consecutive matched sentences grouped into passages — copied sections, not isolated hits"
          >
            Detected passages
          </SectionTitle>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {result.passages.slice(0, 6).map((passage) => (
              <div key={passage.cluster_id} className="card flex items-center gap-3 p-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-navy-900 text-[11px] font-bold text-white">
                  {passage.size}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-semibold text-navy-900">
                    {passage.size} consecutive sentences
                  </p>
                  <p className="mt-0.5 text-[11px] text-navy-500">
                    A ¶{passage.source_span[0] + 1}–¶{passage.source_span[1] + 1} ↔ B ¶
                    {passage.target_span[0] + 1}–¶{passage.target_span[1] + 1}
                  </p>
                </div>
                <span className="tnum shrink-0 text-[12px] font-semibold text-red-700">
                  {(passage.similarity_max * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ------------------------------------------------- paragraph level */}
      {(result.paragraph_matches || []).length > 0 && (
        <div className="mt-3">
          <SectionTitle
            hint="Paragraph vectors are the mean of their sentence vectors — useful when wording changes but the whole argument block is reused"
            action={
              <button
                type="button"
                onClick={() => setShowParagraphs((value) => !value)}
                className="text-[11.5px] font-medium text-accent-700 hover:underline"
              >
                {showParagraphs ? 'Hide' : `Show ${number(paragraphMatches.length)}`}
              </button>
            }
          >
            Paragraph-level similarity
          </SectionTitle>

          {showParagraphs && (
            <div className="card divide-y divide-navy-100">
              {paragraphMatches.slice(0, 8).map((pair) => (
                <div key={pair.id} className="p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[11px] text-navy-500">
                      <span className="rounded border border-navy-200 px-1.5 py-0.5 font-semibold text-navy-700">
                        A ¶{pair.source.paragraph_index + 1}
                      </span>
                      <span className="text-navy-300">↔</span>
                      <span className="rounded border border-navy-200 px-1.5 py-0.5 font-semibold text-navy-700">
                        B ¶{pair.target.paragraph_index + 1}
                      </span>
                      <span className="ml-1 hidden tnum sm:inline">
                        {number(pair.source.word_count)} ↔ {number(pair.target.word_count)} words
                      </span>
                    </span>
                    <span className="flex items-center gap-2">
                      <BandBadge band={pair.band} />
                      <span className="tnum text-[12px] font-semibold text-navy-900">
                        {pair.similarity_pct.toFixed(1)}%
                      </span>
                    </span>
                  </div>
                  <div className="mt-2 grid gap-2 lg:grid-cols-2">
                    <p className="rounded-md border border-navy-100 bg-navy-50/40 p-2 text-[11.5px] leading-relaxed text-navy-700">
                      {pair.source.text}
                    </p>
                    <p className="rounded-md border border-navy-100 bg-navy-50/40 p-2 text-[11.5px] leading-relaxed text-navy-700">
                      {pair.target.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ----------------------------------------------------------- matches */}
      <div className="mt-5">
        <SectionTitle
          hint={`${number(matches.length)} shown · primary matches count once per sentence, alternatives are optional`}
          action={
            <label className="flex cursor-pointer items-center gap-1.5 text-[11.5px] text-navy-500">
              <input
                type="checkbox"
                checked={includeAlternatives}
                onChange={(event) => setIncludeAlternatives(event.target.checked)}
                className="h-3.5 w-3.5 rounded border-navy-300 text-accent-600"
              />
              Show alternative matches
            </label>
          }
        >
          Sentence-level comparisons
        </SectionTitle>

        <div className="card overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-navy-100 bg-navy-50/40 px-3 py-2">
            <div className="flex flex-wrap gap-1">
              {FILTERS.map((item) => {
                const counts = {
                  all: summary.primary_matches,
                  exact: summary.exact_matches,
                  near_exact: summary.near_exact_matches,
                  semantic: summary.semantic_matches,
                  suppressed: summary.suppressed_matches,
                }
                const active = filter === item.key
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setFilter(item.key)}
                    className={`rounded-md px-2 py-1 text-[11.5px] font-medium transition-colors ${
                      active
                        ? 'bg-white text-navy-900 shadow-card ring-1 ring-inset ring-navy-200'
                        : 'text-navy-500 hover:bg-white/70 hover:text-navy-800'
                    }`}
                  >
                    {item.label}
                    <span className="tnum ml-1 text-[10.5px] text-navy-400">{counts[item.key] ?? 0}</span>
                  </button>
                )
              })}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-navy-300" aria-hidden="true" />
                <input
                  className="input h-8 w-44 pl-7 text-[12px]"
                  placeholder="Search passage text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  aria-label="Search matched passages"
                />
              </div>
              <div className="flex items-center gap-1">
                <Filter className="h-3.5 w-3.5 text-navy-300" aria-hidden="true" />
                <select
                  className="input h-8 w-[158px] text-[12px]"
                  value={sort}
                  onChange={(event) => setSort(event.target.value)}
                  aria-label="Sort matches"
                >
                  <option value="similarity">Highest similarity</option>
                  <option value="document">Document order</option>
                </select>
              </div>
            </div>
          </div>

          {matches.length === 0 ? (
            <EmptyState
              icon={Layers}
              title="No matches in this view"
              description={
                filter === 'all' && !search
                  ? 'No sentence pairs reached the similarity threshold. The two documents are textually and semantically distinct at sentence level.'
                  : 'Adjust the filters or clear the search to see other matches.'
              }
            />
          ) : (
            <div>
              {matches.map((match, index) => (
                <MatchItem
                  key={match.id}
                  match={match}
                  index={index}
                  sessionTextAvailable={result.session_text_available}
                  onOpenViewer={() =>
                    navigate(`/analysis/${analysisId}/viewer?match=${match.id}`)
                  }
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ----------------------------------------------------- supplementary */}
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="card p-4">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-navy-900">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
            Processing notes
          </p>
          {result.warnings.length === 0 ? (
            <p className="mt-1.5 text-[12px] text-navy-500">No notes for this comparison.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {result.warnings.map((warning) => (
                <li key={warning} className="flex gap-1.5 text-[12px] leading-relaxed text-navy-600">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-amber-400" aria-hidden="true" />
                  {warning}
                </li>
              ))}
            </ul>
          )}
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-navy-100 pt-2.5 text-[11.5px]">
            <div className="flex justify-between">
              <dt className="text-navy-500">Embedding</dt>
              <dd className="tnum font-medium text-navy-800">{formatDuration(engine.timings.embedding_ms)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-navy-500">Matching</dt>
              <dd className="tnum font-medium text-navy-800">{formatDuration(engine.timings.matching_ms)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-navy-500">Sentences A / B</dt>
              <dd className="tnum font-medium text-navy-800">
                {docs.A.eligible_sentence_count} / {docs.B.eligible_sentence_count}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-navy-500">Model</dt>
              <dd className="truncate font-medium text-navy-800" title={engine.model}>
                {engine.model.split('/').pop()}
              </dd>
            </div>
          </dl>
        </div>

        <div className="card p-4">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-navy-900">
            <ShieldAlert className="h-3.5 w-3.5 text-navy-500" aria-hidden="true" />
            How this was computed
          </p>
          <ul className="mt-2 space-y-1.5 text-[12px] leading-relaxed text-navy-600">
            <li>
              • Every comparable sentence was encoded with{' '}
              <span className="font-mono text-[11.5px]">{engine.model}</span> and compared with cosine
              similarity ({engine.similarity_metric}).
            </li>
            <li>
              • Pairs are classified as exact (identical after normalisation), near-exact (token
              sequence ≥ {thresholds.near_exact_lexical.toFixed(2)}) or semantic (cosine ≥{' '}
              {thresholds.semantic_min.toFixed(2)}).
            </li>
            <li>
              • Reference lists, headings and fragments were excluded; generic academic phrasing and
              citation-only overlap were suppressed or downgraded.
            </li>
            <li>
              • Paragraph-level similarities were also computed from averaged sentence vectors.
            </li>
          </ul>
          <Link to="/methodology" className="link mt-2.5 inline-block text-[12px]">
            Read the full methodology and its limitations
          </Link>
        </div>
      </div>

      <p className="mt-4 text-center text-[11px] text-navy-400">
        Report generated from measured similarity data. {result.retention_minutes} min text retention ·
        identified as <span className="font-mono">{result.analysis_id}</span>
      </p>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this analysis?"
        description="The stored result, match records and any retained document text will be removed. The PDF report can no longer be downloaded afterwards."
        confirmLabel="Delete analysis"
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}
