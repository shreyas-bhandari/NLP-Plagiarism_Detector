import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ShieldCheck,
  Download,
  FileText,
  BarChart3,
  Layers,
  Microscope,
  FileSpreadsheet,
  ChevronRight,
} from 'lucide-react'
import MatchCard from '../components/MatchCard'
import StatCard from '../components/StatCard'
import Collapsible from '../components/Collapsible'

const badgeClassFor = (label) => {
  if (label === 'HIGH SIMILARITY') return 'badge-high'
  if (label === 'MODERATE SIMILARITY') return 'badge-mod'
  return 'badge-low'
}

const labelColor = (label) => {
  if (label === 'HIGH SIMILARITY') return 'text-high'
  if (label === 'MODERATE SIMILARITY') return 'text-mod'
  return 'text-low'
}

export default function ResultPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetch(`/api/result/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error('Result not found.')
        return r.json()
      })
      .then((data) => {
        if (!cancelled) setResult(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [id])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-20 text-center">
        <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
        <p className="text-muted">Analyzing documents…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-20 text-center">
        <p className="text-red text-sm">{error}</p>
        <button
          onClick={() => navigate('/')}
          className="mt-6 btn-outline"
        >
          <ChevronRight size={16} className="mr-2 -ml-1" /> Back to upload
        </button>
      </div>
    )
  }

  const score = result.similarity_score ?? 0
  const label = result.label || 'LOW SIMILARITY'
  const counts = result.counts || {}
  const coverage = result.coverage || {}
  const matches = result.matches || []
  const strongest = matches[0]
  const passages = result.passages || []
  const docA = result.document_a || {}
  const docB = result.document_b || {}

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 lg:py-16">
      <nav className="mb-8 flex items-center gap-2 text-[12px] text-muted">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1 hover:text-accent"
        >
          <ChevronRight size={14} className="-rotate-90" /> Upload
        </button>
        <span className="text-[10px] text-muted uppercase tracking-wider">›</span>
        <span className="text-body">{result.analysis_id}</span>
      </nav>

      {/* ============ HERO RESULT CARD ============ */}
      <div className="card mb-8 relative overflow-hidden">
        <div className="flex items-start justify-between mb-3">
          <div>
            <p className="text-xs font-bold text-muted uppercase tracking-wider">
              Similarity Result
            </p>
            <h2 className="text-4xl font-bold text-ink leading-none">
              {score}%
            </h2>
          </div>
          <span className={`badge ${badgeClassFor(label)} py-1.5 px-3 text-xs`}>
            {label}
          </span>
        </div>
        <p className="text-body text-muted leading-relaxed mb-6">
          {result.explanation || `Based on ${docA.sentences ?? 0} comparable sentences.`}
        </p>

        {/* Compact match counts row */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 pt-4 border-t border-border">
          <div className="bg-slate/40 rounded-lg p-3 text-center">
            <div className="text-xs font-bold text-primary-dark">{counts.semantic ?? 0}</div>
            <div className="text-[10px] text-muted uppercase tracking-wider">Semantic Matches</div>
          </div>
          <div className="bg-slate/40 rounded-lg p-3 text-center">
            <div className="text-xs font-bold text-primary-dark">{counts.exact ?? 0}</div>
            <div className="text-[10px] text-muted uppercase tracking-wider">Exact Matches</div>
          </div>
          <div className="bg-slate/40 rounded-lg p-3 text-center">
            <div className="text-xs font-bold text-primary-dark">{counts.near_exact ?? 0}</div>
            <div className="text-[10px] text-muted uppercase tracking-wider">Near-exact Matches</div>
          </div>
        </div>
      </div>

      {/* ============ WHY FLAGGED — STRONGEST MATCH ============ */}
      <section className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Microscope className="w-5 h-5 text-primary-dark" />
          <h3 className="text-lg font-bold text-ink">Why was it flagged?</h3>
        </div>
        <p className="text-sm text-muted mb-6">
          The strongest signal between the two documents — different wording,
          similar meaning.
        </p>

        <div className="card mb-6 relative">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary" />
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <span className={`badge ${badgeClassFor(strongest.label)} text-xs`}>
                {strongest.score}%
              </span>
              <span className="ml-2 text-xs font-medium text-muted uppercase tracking-wider">
                {strongest.label}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
            <div className="quote-box">
              <span className="quote-label">Document A</span>
              <p className="quote-text">{strongest.sentence_a}</p>
            </div>
            <div className="flex flex-col items-center justify-center lg:col-span-1">
              <span className="text-accent font-mono font-bold text-lg mb-2">&#8595;</span>
              <span className="text-[10px] text-muted uppercase tracking-wider">
                meaning match
              </span>
            </div>
            <div className="quote-box">
              <span className="quote-label">Document B</span>
              <p className="quote-text">{strongest.sentence_b}</p>
            </div>
          </div>
          <p className="mt-5 text-sm text-body leading-relaxed">
            <span className="font-semibold text-high">Different wording.</span>{' '}
            Similar meaning. VeriText detects paraphrased content that
            word-for-word checkers miss.
          </p>
        </div>
      </section>

      {/* ============ OTHER MATCHES ============ */}
      {matches.length > 1 && (
        <section className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-primary-dark" />
              <h3 className="text-lg font-bold text-ink">Other matches</h3>
            </div>
            <span className="text-xs font-bold text-muted uppercase tracking-wider">
              {matches.length - 1} additional
            </span>
          </div>
          <div className="space-y-3">
            {matches.slice(1).map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
        </section>
      )}

      {/* ============ SUMMARY ============ */}
      <section className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-primary-dark" />
          <h3 className="text-lg font-bold text-ink">What did we find?</h3>
        </div>
        <p className="text-sm text-muted mb-6">
          Coverage shows how much of each document has a meaningful match in
          the other.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatCard
            number={`${coverage.a ?? 0}%`}
            label="Document A coverage"
            note="of sentences matched"
          />
          <StatCard
            number={`${coverage.b ?? 0}%`}
            label="Document B coverage"
            note="of sentences matched"
          />
          <StatCard
            number={`${counts.semantic ?? 0}`}
            label="Semantic matches"
            note="meaning-level overlap"
          />
        </div>
      </section>

      {/* ============ DETECTED PASSAGE ============ */}
      {passages.length > 0 && (
        <Collapsible
          title="Detected Passage"
          className="mb-8"
        >
          <div className="space-y-4">
            <div className="bg-slate/40 rounded-lg p-4">
              <div className="text-xs font-bold text-muted uppercase tracking-wider mb-1">
                {passages[0].sentences} consecutive sentences
              </div>
              <div className="text-lg font-bold text-ink">{passages[0].similarity}% similarity</div>
              <p className="text-sm text-muted mt-2">
                A larger section of the documents contains related meaning.
              </p>
            </div>
            <button className="btn-outline w-fit">
              <FileText className="w-4 h-4 mr-2" /> View passage
            </button>
          </div>
        </Collapsible>
      )}

      {/* ============ PARAGRAPH SIMILARITY (SECONDARY) ============ */}
      <Collapsible title="Paragraph-level similarity" className="mb-8">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted uppercase tracking-wider mb-1">
                Compare larger blocks of content.
              </p>
              <p className="text-lg font-bold text-ink">
                {result.paragraph_similarity?.score ?? 0}%
              </p>
              <span className={`badge ${badgeClassFor(result.paragraph_similarity?.label || '')} text-[10px]`}>
                {result.paragraph_similarity?.label || ''}
              </span>
            </div>
          </div>
          <p className="text-sm text-muted">
            Paragraph similarity is a secondary signal and does not drive the
            main result.
          </p>
        </div>
      </Collapsible>

      {/* ============ TECHNICAL DETAILS ============ */}
      <Collapsible title="How was this calculated?" className="mb-8">
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-[12px]">
            <div>
              <div className="text-muted text-[10px] uppercase tracking-wider mb-1">Model</div>
              <div className="text-body">{result.technical?.model ?? 'all-MiniLM-L6-v2'}</div>
            </div>
            <div>
              <div className="text-muted text-[10px] uppercase tracking-wider mb-1">Embedding</div>
              <div className="text-body">{result.technical?.embedding_size ?? 384} dimensions</div>
            </div>
            <div>
              <div className="text-muted text-[10px] uppercase tracking-wider mb-1">Method</div>
              <div className="text-body">Cosine similarity</div>
            </div>
            <div>
              <div className="text-muted text-[10px] uppercase tracking-wider mb-1">Device</div>
              <div className="text-body">{result.technical?.device ?? 'cpu'}</div>
            </div>
          </div>
          <div className="bg-slate/40 rounded-lg p-3 border border-border">
            <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Classification</div>
            <div className="text-body">
              Exact → near-exact → semantic. Lexical evidence (normalized
              string matching) is checked before semantic similarity.
            </div>
          </div>
          <div className="bg-slate/40 rounded-lg p-3 border border-border mt-2">
            <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Thresholds</div>
            <div className="text-body">
              Semantic: {result.technical?.semantic_threshold ?? 0.70}&nbsp;·&nbsp;
              Near-exact: 0.85 lexical similarity&nbsp;·&nbsp;
              Exact: identical normalized text
            </div>
          </div>
          <p className="text-[11px] text-muted mt-3 leading-relaxed">
            Similarity does not prove plagiarism. Results should be reviewed by
            a human. Intent cannot be determined automatically.
          </p>
        </div>
      </Collapsible>

      {/* ============ EXPORTS ============ */}
      <section className="mb-10 border-t border-border pt-8 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div className="flex items-center gap-4">
          <a
            href={`/api/result/${id}/json`}
            download
            className="btn-outline"
          >
            <FileSpreadsheet className="w-4 h-4 mr-2" /> Export JSON
          </a>
          <a
            href={`/api/result/${id}/pdf`}
            download
            className="btn-primary"
          >
            <Download className="w-4 h-4 mr-2" /> Export PDF Report
          </a>
        </div>
        <p className="text-[11px] text-muted leading-relaxed sm:mt-0 mt-3">
          PDF is designed for humans. JSON is the machine-readable structured
          result for APIs, storage and integrations.
        </p>
      </section>

      <p className="text-[11px] text-muted text-center">
        Similarity does not prove plagiarism. Results should be reviewed by a
        human.
      </p>
    </div>
  )
}
