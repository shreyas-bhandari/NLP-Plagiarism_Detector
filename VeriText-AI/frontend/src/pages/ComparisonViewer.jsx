import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Columns2,
  Eye,
  EyeOff,
  Info,
  Rows3,
} from 'lucide-react'
import { useRequest } from '../hooks/useRequest'
import { getAnalysis, getAnalysisDocuments } from '../services/api'
import { Callout, EmptyState, Spinner } from '../components/Primitives'
import { ClassificationBadge } from '../components/Badge'
import { classificationMeta, matchPalette } from '../utils/similarity'
import { number } from '../utils/format'

/**
 * Side-by-side comparison viewer.
 *
 * Left panel: Document A. Right panel: Document B. Every matched sentence is
 * highlighted with the colour assigned to its match, and both members of the pair
 * share that colour, so a reviewer can see the correspondence without reading
 * scores. Navigation jumps between matches in similarity order.
 */
export default function ComparisonViewer() {
  const { analysisId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const docsRequest = useRequest(() => getAnalysisDocuments(analysisId), [analysisId])
  const analysisRequest = useRequest(() => getAnalysis(analysisId), [analysisId])

  const [onlyMatched, setOnlyMatched] = useState(false)
  const sentenceRefs = useRef(new Map())

  const primaryMatches = useMemo(() => {
    const list = analysisRequest.data?.matches || []
    return list
      .filter((match) => match.is_primary && !match.suppressed)
      .sort((a, b) => b.similarity - a.similarity)
  }, [analysisRequest.data])

  const matchById = useMemo(() => {
    const map = new Map()
    ;(analysisRequest.data?.matches || []).forEach((match) => map.set(match.id, match))
    return map
  }, [analysisRequest.data])

  const orderIndex = useMemo(() => {
    const map = new Map()
    primaryMatches.forEach((match, index) => map.set(match.id, index))
    return map
  }, [primaryMatches])

  const [activeId, setActiveId] = useState(() => searchParams.get('match') || null)

  useEffect(() => {
    if (!activeId && primaryMatches.length > 0) setActiveId(primaryMatches[0].id)
  }, [primaryMatches, activeId])

  useEffect(() => {
    if (activeId) setSearchParams({ match: activeId }, { replace: true })
  }, [activeId, setSearchParams])

  const activeMatch = activeId ? matchById.get(activeId) : null
  const activePosition = activeMatch ? primaryMatches.findIndex((match) => match.id === activeMatch.id) : -1

  // Highlight maps: every sentence that appears in the active match list.
  const { highlightsA, highlightsB } = useMemo(() => {
    const a = new Map()
    const b = new Map()
    primaryMatches.forEach((match) => {
      a.set(match.source.sentence_id, match)
      b.set(match.target.sentence_id, match)
    })
    return { highlightsA: a, highlightsB: b }
  }, [primaryMatches])

  const goTo = (offset) => {
    if (primaryMatches.length === 0) return
    const next = Math.max(0, Math.min(primaryMatches.length - 1, activePosition + offset))
    setActiveId(primaryMatches[next].id)
  }

  /**
   * Scroll *inside* each panel instead of using scrollIntoView, which would also
   * move the browser window and push the page header out of view.
   */
  const scrollToSentence = (label, sentenceId) => {
    const element = sentenceRefs.current.get(`${label}:${sentenceId}`)
    const container = element?.closest('[data-scroll-panel]')
    if (!element || !container) return
    const elementRect = element.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    const target =
      container.scrollTop + (elementRect.top - containerRect.top) -
      container.clientHeight / 2 + element.offsetHeight / 2
    container.scrollTo({ top: Math.max(0, target), behavior: 'smooth' })
  }

  useEffect(() => {
    if (!activeMatch) return
    scrollToSentence('A', activeMatch.source.sentence_id)
    scrollToSentence('B', activeMatch.target.sentence_id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMatch])

  useEffect(() => {
    const onKey = (event) => {
      if (event.target instanceof HTMLInputElement) return
      if (event.key === 'j' || event.key === 'ArrowRight') goTo(1)
      if (event.key === 'k' || event.key === 'ArrowLeft') goTo(-1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const loading = docsRequest.loading || analysisRequest.loading
  const error = docsRequest.error || analysisRequest.error

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-[13px] text-navy-500">
        <Spinner className="mr-2 h-4 w-4" /> Loading document text…
      </div>
    )
  }

  if (error) {
    const expired = error.status === 410
    return (
      <div className="mx-auto max-w-2xl">
        <div className="card p-6">
          <EmptyState
            icon={Info}
            title={expired ? 'Document text is no longer retained' : 'Could not load the viewer'}
            description={
              expired
                ? `For privacy, extracted text is deleted ${analysisRequest.data?.retention_minutes || 120} minutes after analysis. The scores, matches and PDF report remain available.`
                : `${error.message} ${error.hint || ''}`
            }
            action={
              <Link to={`/analysis/${analysisId}`} className="btn btn-primary btn-md">
                Back to results
              </Link>
            }
          />
        </div>
      </div>
    )
  }

  const payload = docsRequest.data
  if (!payload) return null

  const renderDocument = (label) => {
    const doc = payload[label]
    const highlights = label === 'A' ? highlightsA : highlightsB
    const sentencesById = new Map(doc.sentences.map((sentence) => [sentence.id, sentence]))

    return (
      <div className="flex min-h-0 flex-col border-navy-100 bg-white lg:h-[calc(100vh-13.5rem)] lg:border-r lg:last:border-r-0">
        <div className="sticky top-0 z-10 border-b border-navy-100 bg-white/95 px-3.5 py-2.5 backdrop-blur">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-navy-900 text-[10px] font-bold text-white">
                {label}
              </span>
              <p className="truncate text-[12.5px] font-semibold text-navy-900" title={doc.filename}>
                {doc.filename}
              </p>
            </div>
            <span className="shrink-0 text-[10.5px] text-navy-400">
              {number(doc.eligible_sentence_count)} comparable sentences
            </span>
          </div>
        </div>

        <div data-scroll-panel className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 py-3.5">
          {doc.paragraphs.map((paragraph) => {
            const paragraphSentences = paragraph.sentence_ids
              .map((id) => sentencesById.get(id))
              .filter(Boolean)
            if (paragraphSentences.length === 0) return null

            const visible = onlyMatched
              ? paragraphSentences.filter((sentence) => highlights.has(sentence.id))
              : paragraphSentences
            if (visible.length === 0) return null

            if (paragraph.is_heading) {
              return (
                <h3
                  key={paragraph.id}
                  className="mb-2 mt-4 text-[12.5px] font-semibold uppercase tracking-wide text-navy-700 first:mt-0"
                >
                  {paragraph.text}
                </h3>
              )
            }

            return (
              <div key={paragraph.id} className="mb-3.5">
                <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-navy-300">
                  ¶{paragraph.index + 1}
                  {paragraph.page ? ` · p.${paragraph.page}` : ''}
                  {paragraph.section === 'references' ? ' · references (excluded)' : ''}
                </p>
                <p className="snippet">
                  {visible.map((sentence) => {
                    const match = highlights.get(sentence.id)
                    const isActive = match && match.id === activeMatch?.id
                    const key = `${label}:${sentence.id}`
                    if (!match) {
                      return (
                        <span
                          key={sentence.id}
                          ref={(element) => {
                            if (element) sentenceRefs.current.set(key, element)
                          }}
                          className={sentence.eligible ? '' : 'text-navy-400'}
                        >
                          {sentence.text}{' '}
                        </span>
                      )
                    }
                    const palette = matchPalette(orderIndex.get(match.id) ?? 0)
                    return (
                      <span
                        key={sentence.id}
                        ref={(element) => {
                          if (element) sentenceRefs.current.set(key, element)
                        }}
                        role="button"
                        tabIndex={0}
                        onClick={() => setActiveId(match.id)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') setActiveId(match.id)
                        }}
                        className={`hl cursor-pointer ${palette.bg} ${palette.text} ${
                          isActive ? `ring-2 ring-offset-1 ${palette.ring}` : ''
                        }`}
                        title={`Match ${(orderIndex.get(match.id) ?? 0) + 1} · ${match.similarity_pct}% · ${match.classification_label}`}
                      >
                        {sentence.text}{' '}
                        <sup className="ml-0.5 font-mono text-[9px] font-bold opacity-60">
                          {(orderIndex.get(match.id) ?? 0) + 1}
                        </sup>
                      </span>
                    )
                  })}
                </p>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/analysis/${analysisId}`}
            className="inline-flex items-center gap-1 text-[11.5px] font-medium text-navy-400 hover:text-navy-700"
          >
            <ArrowLeft className="h-3 w-3" aria-hidden="true" />
            Back to results
          </Link>
          <h1 className="mt-1 flex items-center gap-2 text-[19px] font-semibold tracking-[-0.02em] text-navy-900">
            <Columns2 className="h-4 w-4 text-navy-400" aria-hidden="true" />
            Side-by-side comparison
          </h1>
          <p className="mt-0.5 text-[12px] text-navy-500">
            {primaryMatches.length} primary match{primaryMatches.length === 1 ? '' : 'es'} highlighted in
            both documents. Click a highlight to inspect it, or use the arrow keys.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setOnlyMatched((value) => !value)}
          >
            {onlyMatched ? <Eye className="h-3.5 w-3.5" aria-hidden="true" /> : <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />}
            {onlyMatched ? 'Show full text' : 'Only matched'}
          </button>
          <div className="flex items-center rounded-lg border border-navy-200 bg-white">
            <button
              type="button"
              className="flex h-8 w-8 items-center justify-center rounded-l-lg text-navy-500 hover:bg-navy-50 disabled:opacity-40"
              onClick={() => goTo(-1)}
              disabled={activePosition <= 0}
              aria-label="Previous match"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="tnum min-w-[64px] border-x border-navy-100 px-2 text-center text-[11.5px] font-medium text-navy-700">
              {activePosition >= 0 ? activePosition + 1 : 0} / {primaryMatches.length}
            </span>
            <button
              type="button"
              className="flex h-8 w-8 items-center justify-center rounded-r-lg text-navy-500 hover:bg-navy-50 disabled:opacity-40"
              onClick={() => goTo(1)}
              disabled={activePosition >= primaryMatches.length - 1}
              aria-label="Next match"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* active match bar */}
      {activeMatch && (
        <div className="card mt-3 flex flex-wrap items-center gap-3 px-4 py-2.5">
          <span className="rounded-md bg-navy-900 px-1.5 py-0.5 text-[11px] font-bold text-white">
            #{activePosition + 1}
          </span>
          <ClassificationBadge classification={activeMatch.classification} />
          <span className="tnum text-[13px] font-semibold text-navy-900">
            {activeMatch.similarity_pct.toFixed(1)}% cosine
          </span>
          <span className="hidden text-[11.5px] text-navy-400 sm:inline">
            token Jaccard {activeMatch.signals.token_jaccard.toFixed(2)} · sequence{' '}
            {activeMatch.signals.sequence_ratio.toFixed(2)} · {activeMatch.evidence_strength} evidence
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Link
              to={`/analysis/${analysisId}`}
              className="btn btn-quiet btn-sm"
              title="Open the detailed evidence panel for this match"
            >
              <Rows3 className="h-3.5 w-3.5" aria-hidden="true" />
              Evidence
            </Link>
          </div>
        </div>
      )}

      <div className="mt-2.5">
        <Callout tone="info">
          Highlights share a colour between the two panels. Text in grey was excluded from matching
          (headings, reference lists or very short fragments). Similarity is not proof of copying.
        </Callout>
      </div>

      <div className="mt-3 grid overflow-hidden rounded-card border border-navy-100 bg-white shadow-card lg:grid-cols-2">
        {renderDocument('A')}
        {renderDocument('B')}
      </div>

      <p className="mt-3 text-center text-[11px] text-navy-400">
        Retention: this text is deleted {payload.retention_minutes} minutes after the analysis was run, or
        immediately when the analysis is deleted. {classificationMeta('semantic').description}
      </p>
    </div>
  )
}
