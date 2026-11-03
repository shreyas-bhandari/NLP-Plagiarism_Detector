import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

const scoreVariant = (score) => {
  if (score >= 70) return 'badge-high'
  if (score >= 50) return 'badge-mod'
  return 'badge-low'
}

export default function MatchCard({ match, showAxes = false }) {
  const [expanded, setExpanded] = useState(false)
  const { score, label, type, sentence_a, sentence_b } = match

  return (
    <div className="card mb-4">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex flex-col lg:flex-row lg:items-start gap-3 lg:gap-4 lg:px-0"
      >
        <div className="flex items-center gap-2 mb-3 lg:mb-0 lg:w-48 lg:flex-shrink-0">
          <span className={`badge ${scoreVariant(score)}`}>
            {score}%
          </span>
          <span className="text-xs font-medium text-muted uppercase tracking-wider">
            {type.replace('_', ' ')}
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <h4 className="text-base font-bold text-ink leading-snug mb-1">
            {label}
          </h4>
          <p className="text-sm text-body line-clamp-2 mb-3 lg:mb-0">
            “{sentence_a}”
          </p>
          <p className="text-xs text-muted">
            ↕&nbsp; <span className="font-medium text-ink line-clamp-1">
              “{sentence_b}”
            </span>
          </p>
        </div>

        <button
          className="ml-3 lg:ml-0 flex-shrink-0 text-accent font-medium hover:underline"
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown size={16} className="mr-1" /> : <ChevronRight size={16} className="mr-1" />}
          {expanded ? 'Hide comparison' : 'View comparison'}
        </button>
      </button>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-border grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="quote-box">
            <span className="quote-label">Document A</span>
            <p className="quote-text">{sentence_a}</p>
          </div>
          <div className="flex items-center justify-center">
            <span className="text-accent font-mono font-bold text-lg">&#8595;</span>
          </div>
          <div className="quote-box">
            <span className="quote-label">Document B</span>
            <p className="quote-text">{sentence_b}</p>
          </div>
        </div>
      )}
    </div>
  )
}
