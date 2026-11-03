import { useState } from 'react'
import {
  ChevronDown,
  Columns2,
  Info,
  Link2,
  MapPin,
  Quote,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { ClassificationBadge, StrengthBadge, SuppressedBadge } from './Badge'
import ScoreBar from './ScoreBar'
import { SUPPRESS_REASON_LABELS, bandMeta, classificationMeta, strengthMeta } from '../utils/similarity'
import { number } from '../utils/format'

function Location({ sentence }) {
  const parts = [`¶${number((sentence.paragraph ?? 0) + 1)}`, `sentence ${number(sentence.index + 1)}`]
  if (sentence.page) parts.push(`page ${sentence.page}`)
  if (sentence.section && sentence.section !== 'body') parts.push(sentence.section)
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-navy-400">
      <MapPin className="h-3 w-3" aria-hidden="true" />
      {parts.join(' · ')}
    </span>
  )
}

/**
 * One match, expandable into its evidence.
 *
 * The collapsed row answers "what matched?" (passage text + score); the expanded
 * panel answers "why was it flagged?" (signals, shared terms, verbatim run,
 * caveat). This is the explainability core of the results page.
 */
export default function MatchItem({ match, index, sessionTextAvailable, onOpenViewer }) {
  const [open, setOpen] = useState(false)
  const meta = classificationMeta(match.classification)
  const strength = strengthMeta(match.evidence_strength)
  const signals = match.signals || {}
  const explanation = match.explanation || {}
  const cluster = match.cluster

  return (
    <div
      className={`group border-b border-navy-100 last:border-b-0 ${
        match.suppressed ? 'bg-navy-50/40' : 'bg-white'
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-navy-50/50"
      >
        <span
          className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[11px] font-bold ${
            match.suppressed ? 'bg-navy-100 text-navy-500' : `${meta.bg} ${meta.text}`
          }`}
        >
          {index + 1}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <ClassificationBadge classification={match.classification} compact />
            {!match.suppressed && <StrengthBadge strength={match.evidence_strength} />}
            {match.suppressed && (
              <SuppressedBadge
                reason={SUPPRESS_REASON_LABELS[match.suppress_reason] || match.suppress_reason}
                label={`Suppressed · ${SUPPRESS_REASON_LABELS[match.suppress_reason] || 'low evidence'}`}
              />
            )}
            {cluster?.size > 1 && (
              <span className="inline-flex items-center gap-1 rounded-md border border-navy-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-navy-600">
                <Link2 className="h-3 w-3" aria-hidden="true" />
                Passage of {cluster.size}
              </span>
            )}
            {match.mutual_best && (
              <span className="inline-flex items-center gap-1 rounded-md border border-accent-200 bg-accent-50 px-1.5 py-0.5 text-[11px] font-medium text-accent-700">
                <Sparkles className="h-3 w-3" aria-hidden="true" />
                Mutual best
              </span>
            )}
            {match.subtype === 'paraphrase' && (
              <span className="rounded-md border border-accent-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-accent-700">
                Paraphrase pattern
              </span>
            )}
            {match.is_primary === false && (
              <span className="rounded-md border border-navy-200 bg-white px-1.5 py-0.5 text-[11px] text-navy-500">
                alternative match
              </span>
            )}
          </div>

          <div className="mt-2 space-y-1">
            <p className="line-clamp-2 text-[12.5px] leading-snug text-navy-800">
              <span className="mr-1.5 font-semibold text-navy-400">A</span>
              {match.source.text}
            </p>
            <p className="line-clamp-2 text-[12.5px] leading-snug text-navy-600">
              <span className="mr-1.5 font-semibold text-navy-400">B</span>
              {match.target.text}
            </p>
          </div>
        </div>

        <div className="flex w-[132px] shrink-0 flex-col items-end gap-1.5">
          <ScoreBar value={match.similarity} band={match.band} size="sm" />
          <span className="text-[10.5px] font-medium uppercase tracking-wide text-navy-400">
            {bandMeta(match.band).label} similarity
          </span>
        </div>

        <ChevronDown
          className={`mt-1 h-4 w-4 shrink-0 text-navy-300 transition-transform group-hover:text-navy-500 ${
            open ? 'rotate-180' : ''
          }`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="animate-fade-up border-t border-navy-100 bg-navy-50/30 px-4 py-4">
          <div className="grid gap-3 md:grid-cols-2">
            {[
              { key: 'A', sentence: match.source, tone: 'border-red-200 bg-red-50/40' },
              { key: 'B', sentence: match.target, tone: 'border-accent-200 bg-accent-50/40' },
            ].map(({ key, sentence, tone }) => (
              <div key={key} className={`rounded-lg border bg-white p-3 ${tone}`}>
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="label-micro">Document {key}</span>
                  <Location sentence={sentence} />
                </div>
                <p className="snippet">{sentence.text}</p>
              </div>
            ))}
          </div>

          <div className="mt-3 rounded-lg border border-navy-200 bg-white p-3">
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-600" aria-hidden="true" />
              <div className="min-w-0">
                <p className="text-[12.5px] font-semibold text-navy-900">
                  {explanation.headline || meta.description}
                </p>
                <ul className="mt-1.5 space-y-1">
                  {(explanation.reasons || []).map((reason) => (
                    <li key={reason} className="flex gap-1.5 text-[12px] leading-relaxed text-navy-600">
                      <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-navy-300" aria-hidden="true" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {(explanation.shared_terms || []).length > 0 && (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span className="label-micro">Shared distinctive terms</span>
                {explanation.shared_terms.map((term) => (
                  <span
                    key={term}
                    className="rounded border border-navy-200 bg-navy-50 px-1.5 py-0.5 text-[11px] font-medium text-navy-700"
                  >
                    {term}
                  </span>
                ))}
              </div>
            )}

            {explanation.verbatim_run && explanation.verbatim_words >= 4 && (
              <div className="mt-2.5 rounded-md border border-navy-100 bg-navy-50/60 p-2">
                <p className="label-micro mb-1 flex items-center gap-1">
                  <Quote className="h-3 w-3" aria-hidden="true" />
                  Longest verbatim run · {explanation.verbatim_words} words
                </p>
                <p className="text-[12px] italic leading-snug text-navy-700">
                  “{explanation.verbatim_run}”
                </p>
              </div>
            )}

            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-navy-100 pt-2.5 sm:grid-cols-4">
              {[
                { label: 'Cosine', value: signals.cosine?.toFixed(3) },
                { label: 'Token Jaccard', value: signals.token_jaccard?.toFixed(3) },
                { label: 'Sequence ratio', value: signals.sequence_ratio?.toFixed(3) },
                { label: 'Shared content', value: `${signals.shared_token_count ?? 0} tokens` },
              ].map((item) => (
                <div key={item.label}>
                  <dt className="text-[10.5px] uppercase tracking-wide text-navy-400">{item.label}</dt>
                  <dd className="tnum text-[12px] font-semibold text-navy-800">{item.value ?? '—'}</dd>
                </div>
              ))}
            </dl>

            {match.suppressed && (
              <p className="mt-2.5 flex items-start gap-1.5 rounded-md border border-navy-200 bg-navy-50 px-2 py-1.5 text-[11.5px] text-navy-600">
                <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                Excluded from headline metrics: {SUPPRESS_REASON_LABELS[match.suppress_reason] || 'low evidence'}.
                It remains visible so nothing is hidden from you.
              </p>
            )}

            <p className="mt-2.5 text-[11px] leading-relaxed text-navy-400">{explanation.caveat}</p>

            {sessionTextAvailable && onOpenViewer && (
              <button
                type="button"
                className="btn btn-ghost btn-sm mt-2.5"
                onClick={() => onOpenViewer(match)}
              >
                <Columns2 className="h-3.5 w-3.5" aria-hidden="true" />
                Open in side-by-side viewer
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
