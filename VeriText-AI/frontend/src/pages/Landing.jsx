import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Binary,
  BookOpenCheck,
  Braces,
  CheckCircle2,
  FileSearch,
  Fingerprint,
  Gauge,
  GitCompareArrows,
  Layers,
  Lock,
  Quote,
  ScanText,
  ShieldCheck,
  Sigma,
  Sparkles,
  SplitSquareVertical,
  TriangleAlert,
} from 'lucide-react'
import Logo from '../components/Logo'

const FEATURES = [
  {
    icon: SplitSquareVertical,
    title: 'Semantic, not just lexical',
    body: 'MiniLM sentence embeddings compare meaning, so a rewritten paragraph still surfaces next to its source.',
  },
  {
    icon: Fingerprint,
    title: 'Exact and near-exact detection',
    body: 'Verbatim and lightly edited passages are separated from paraphrases, because they are different evidence.',
  },
  {
    icon: Quote,
    title: 'Explainable flags',
    body: 'Every match shows the cosine score, lexical overlap, shared distinctive terms and the verbatim run that triggered it.',
  },
  {
    icon: Layers,
    title: 'Passage grouping',
    body: 'Consecutive matched sentences are clustered into passages, so you review a copied section rather than loose sentences.',
  },
  {
    icon: ShieldCheck,
    title: 'Safeguards against noise',
    body: 'Reference lists, headings, generic phrasing and citation-only overlap are excluded or explicitly downgraded.',
  },
  {
    icon: Lock,
    title: 'Documents stay yours',
    body: 'Text is extracted in memory, never executed, deleted after analysis, and only scores plus short snippets persist.',
  },
]

const STEPS = [
  {
    icon: ScanText,
    title: 'Extract',
    body: 'PyMuPDF and python-docx recover paragraphs while preserving document position for later highlighting.',
  },
  {
    icon: Braces,
    title: 'Segment',
    body: 'An abbreviation-aware splitter produces sentences; headings, fragments and reference lists are held back.',
  },
  {
    icon: Binary,
    title: 'Encode',
    body: 'A pretrained transformer maps each sentence to a 384-dimensional unit vector in a single batched pass.',
  },
  {
    icon: Sigma,
    title: 'Compare',
    body: 'Cosine similarity ranks every sentence against the other document, then lexical evidence classifies the pair.',
  },
]

function PipelineDiagram() {
  return (
    <div className="rounded-xl border border-navy-800/60 bg-navy-950 p-4 shadow-pop">
      <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
        <p className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-white/40">
          Comparison pipeline
        </p>
        <span className="rounded border border-white/15 px-1.5 py-0.5 text-[10px] font-medium text-white/50">
          GPU / CPU · local inference
        </span>
      </div>

      <svg viewBox="0 0 420 232" className="mt-3 w-full" role="img" aria-label="Diagram of the VeriText AI comparison pipeline">
        <defs>
          <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0 0 L7 3.5 L0 7 z" fill="rgba(255,255,255,0.35)" />
          </marker>
        </defs>

        {/* documents */}
        {[
          { y: 22, label: 'Document A', sub: 'PDF / DOCX' },
          { y: 96, label: 'Document B', sub: 'PDF / DOCX' },
        ].map((doc) => (
          <g key={doc.label}>
            <rect x="4" y={doc.y} width="96" height="52" rx="6" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.14)" />
            <text x="14" y={doc.y + 22} fill="rgba(255,255,255,0.85)" fontSize="10.5" fontWeight="600">
              {doc.label}
            </text>
            <text x="14" y={doc.y + 37} fill="rgba(255,255,255,0.4)" fontSize="9">
              {doc.sub}
            </text>
          </g>
        ))}

        <line x1="102" y1="48" x2="140" y2="48" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arrow)" />
        <line x1="102" y1="122" x2="140" y2="122" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arrow)" />

        {/* segmentation */}
        <rect x="142" y="34" width="112" height="102" rx="6" fill="rgba(37,99,235,0.16)" stroke="rgba(96,165,250,0.5)" />
        <text x="152" y="52" fill="#bfdbfe" fontSize="10" fontWeight="600">Sentence split</text>
        {[0, 1, 2, 3].map((row) => (
          <rect key={row} x="152" y={60 + row * 14} width={88 - row * 12} height="5" rx="2.5" fill="rgba(191,219,254,0.5)" />
        ))}
        <text x="152" y="128" fill="rgba(191,219,254,0.65)" fontSize="8.5">abbreviation aware</text>

        <line x1="256" y1="85" x2="286" y2="85" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arrow)" />

        {/* encoder */}
        <rect x="288" y="30" width="124" height="110" rx="6" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.16)" />
        <text x="298" y="48" fill="rgba(255,255,255,0.85)" fontSize="10" fontWeight="600">MiniLM encoder</text>
        <text x="298" y="61" fill="rgba(255,255,255,0.4)" fontSize="8.5">6 layers · 384 dims</text>
        {[0, 1, 2].map((row) => (
          <g key={row}>
            {[0, 1, 2, 3, 4, 5].map((col) => {
              const intensity = 0.15 + ((row * 7 + col * 3) % 8) / 12
              return (
                <rect
                  key={col}
                  x={300 + col * 18}
                  y={72 + row * 20}
                  width="14"
                  height="14"
                  rx="2.5"
                  fill={`rgba(37,99,235,${intensity.toFixed(2)})`}
                  stroke="rgba(96,165,250,0.35)"
                  strokeWidth="0.5"
                />
              )
            })}
          </g>
        ))}
        <text x="298" y="133" fill="rgba(255,255,255,0.4)" fontSize="8.5">v ∈ ℝ³⁸⁴, ‖v‖ = 1</text>

        {/* cosine */}
        <line x1="288" y1="168" x2="252" y2="196" stroke="rgba(255,255,255,0.25)" strokeWidth="1" markerEnd="url(#arrow)" />
        <rect x="122" y="176" width="132" height="48" rx="6" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.16)" />
        <text x="132" y="196" fill="rgba(255,255,255,0.85)" fontSize="10" fontWeight="600">Cosine similarity</text>
        <text x="132" y="211" fill="rgba(255,255,255,0.45)" fontSize="8.5">(A·B)/(‖A‖‖B‖) · lexical check</text>

        {/* verdict */}
        <line x1="256" y1="200" x2="286" y2="200" stroke="rgba(255,255,255,0.25)" strokeWidth="1" markerEnd="url(#arrow)" />
        <rect x="288" y="176" width="124" height="48" rx="6" fill="rgba(21,128,61,0.16)" stroke="rgba(52,211,153,0.45)" />
        <text x="298" y="196" fill="#a7f3d0" fontSize="10" fontWeight="600">Explainable match</text>
        <text x="298" y="211" fill="rgba(167,243,208,0.6)" fontSize="8.5">score · evidence · caveat</text>
      </svg>
    </div>
  )
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-white">
      {/* ------------------------------------------------------------- header */}
      <header className="sticky top-0 z-30 border-b border-navy-100 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Logo to="/" />
          <nav className="hidden items-center gap-6 text-[13px] font-medium text-navy-600 md:flex" aria-label="Site">
            <a href="#how-it-works" className="hover:text-navy-900">How it works</a>
            <a href="#features" className="hover:text-navy-900">Features</a>
            <a href="#nlp" className="hover:text-navy-900">NLP engine</a>
            <Link to="/methodology" className="hover:text-navy-900">Methodology</Link>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/dashboard" className="btn btn-ghost btn-sm hidden sm:inline-flex">
              Dashboard
            </Link>
            <Link to="/analysis/new" className="btn btn-primary btn-sm">
              Start analysis
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </header>

      {/* --------------------------------------------------------------- hero */}
      <section className="relative overflow-hidden bg-navy-950">
        <div className="grid-texture absolute inset-0" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-6xl gap-10 px-5 py-14 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-20">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.06] px-2.5 py-1 text-[11px] font-semibold text-white/70">
              <Sparkles className="h-3 w-3 text-accent-300" aria-hidden="true" />
              Semantic similarity analysis for academic documents
            </span>
            <h1 className="mt-5 text-[34px] font-semibold leading-[1.1] tracking-[-0.025em] text-white sm:text-[44px]">
              Academic integrity,
              <br />
              <span className="text-accent-300">understood beyond words.</span>
            </h1>
            <p className="mt-4 max-w-xl text-[14.5px] leading-relaxed text-white/60">
              VeriText AI compares two documents with sentence embeddings and lexical evidence to
              surface copied, lightly edited and paraphrased passages — with the reasoning shown for
              every flag, not just a number.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-2.5">
              <Link to="/analysis/new" className="btn btn-accent btn-md">
                Compare two documents
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
              <Link
                to="/methodology"
                className="btn btn-md border border-white/20 bg-white/[0.06] text-white hover:bg-white/[0.12]"
              >
                <BookOpenCheck className="h-3.5 w-3.5" aria-hidden="true" />
                How the engine works
              </Link>
            </div>
            <ul className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-[11.5px] text-white/45">
              {[
                'all-MiniLM-L6-v2 · 384 dimensions',
                'Runs locally — GPU when available',
                'No document retention',
              ].map((item) => (
                <li key={item} className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <PipelineDiagram />
        </div>
      </section>

      {/* ------------------------------------------------------------ problem */}
      <section className="border-b border-navy-100 bg-white">
        <div className="mx-auto grid max-w-6xl gap-8 px-5 py-12 md:grid-cols-3">
          {[
            {
              icon: FileSearch,
              title: 'String matching has a blind spot',
              body: 'Replace a few words and an n-gram score collapses to almost zero, even when the argument is unchanged.',
            },
            {
              icon: GitCompareArrows,
              title: 'Meaning survives rewriting',
              body: 'Sentence embeddings place a paraphrase near its source in vector space, so the connection stays visible.',
            },
            {
              icon: Gauge,
              title: 'Scores are not verdicts',
              body: 'A similarity score tells you where to look. It never establishes intent, and VeriText AI never claims it does.',
            },
          ].map(({ icon: Icon, title, body }) => (
            <div key={title}>
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-navy-50 text-navy-700">
                <Icon className="h-4 w-4" aria-hidden="true" />
              </span>
              <h3 className="mt-3 text-[14px] font-semibold text-navy-900">{title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-navy-500">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------- how it works */}
      <section id="how-it-works" className="bg-[#f8fafc] py-14">
        <div className="mx-auto max-w-6xl px-5">
          <p className="label-micro">How it works</p>
          <h2 className="mt-1.5 text-[24px] font-semibold tracking-[-0.02em] text-navy-900">
            Four deterministic stages, one explainable result
          </h2>
          <p className="mt-2 max-w-2xl text-[13.5px] leading-relaxed text-navy-500">
            No model training, no opaque third-party service. The same pipeline runs for every
            comparison and every step is inspectable.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ icon: Icon, title, body }, index) => (
              <div key={title} className="card p-4">
                <div className="flex items-center justify-between">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-navy-900 text-white">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="tnum text-[11px] font-semibold text-navy-300">0{index + 1}</span>
                </div>
                <h3 className="mt-3 text-[13.5px] font-semibold text-navy-900">{title}</h3>
                <p className="mt-1 text-[12.5px] leading-relaxed text-navy-500">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------- features */}
      <section id="features" className="bg-white py-14">
        <div className="mx-auto max-w-6xl px-5">
          <p className="label-micro">Capabilities</p>
          <h2 className="mt-1.5 text-[24px] font-semibold tracking-[-0.02em] text-navy-900">
            Built for review work, not for demos
          </h2>
          <div className="mt-8 grid gap-x-8 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="border-t border-navy-100 pt-4">
                <Icon className="h-4 w-4 text-accent-600" aria-hidden="true" />
                <h3 className="mt-2.5 text-[13.5px] font-semibold text-navy-900">{title}</h3>
                <p className="mt-1 text-[12.5px] leading-relaxed text-navy-500">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- nlp */}
      <section id="nlp" className="border-y border-navy-100 bg-navy-950 py-14 text-white">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 lg:grid-cols-[1fr_0.9fr]">
          <div>
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-accent-300">
              The NLP engine
            </p>
            <h2 className="mt-2 text-[24px] font-semibold tracking-[-0.02em]">
              A pretrained transformer, used honestly
            </h2>
            <p className="mt-3 text-[13.5px] leading-relaxed text-white/60">
              Each sentence becomes a single 384-dimensional vector produced by
              <span className="font-mono text-[12.5px] text-white/85"> sentence-transformers/all-MiniLM-L6-v2</span>.
              Vectors are L2-normalised, so the cosine similarity of two sentences is simply their
              dot product. The model is loaded once at startup and reused — it is never trained or
              fine-tuned here.
            </p>
            <div className="mt-5 rounded-lg border border-white/15 bg-white/[0.05] px-4 py-3">
              <p className="font-mono text-[12.5px] text-white/85">
                cos(A, B) = (A · B) / (‖A‖ · ‖B‖)
              </p>
              <p className="mt-1.5 text-[11.5px] text-white/45">
                With ‖A‖ = ‖B‖ = 1 this reduces to A · B — exactly what the engine computes on the
                similarity matrix.
              </p>
            </div>
            <Link to="/methodology" className="btn btn-sm mt-5 border border-white/20 bg-white/[0.06] text-white hover:bg-white/[0.12]">
              Read the full methodology
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>

          <div className="space-y-3">
            <div className="rounded-lg border border-white/12 bg-white/[0.04] p-4">
              <div className="flex items-start gap-2.5">
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
                <div>
                  <p className="text-[12.5px] font-semibold text-white/90">What it will not tell you</p>
                  <ul className="mt-1.5 space-y-1 text-[11.5px] leading-relaxed text-white/50">
                    <li>• whether copying was intentional</li>
                    <li>• whether an unsupplied source was used</li>
                    <li>• whether a passage needed a citation</li>
                    <li>• a single “plagiarism percentage”</li>
                  </ul>
                </div>
              </div>
            </div>
            <div className="rounded-lg border border-white/12 bg-white/[0.04] p-4">
              <p className="text-[12.5px] font-semibold text-white/90">Where it is weakest</p>
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-white/50">
                Heavy paraphrase, textbook definitions and standard methodology sentences are the
                hard cases. The engine marks them explicitly as weak or definition-shaped evidence
                instead of hiding the difficulty in an aggregate score.
              </p>
            </div>
            <div className="rounded-lg border border-white/12 bg-white/[0.04] p-4">
              <p className="text-[12.5px] font-semibold text-white/90">Measured, not claimed</p>
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-white/50">
                The repository ships a labelled evaluation set and the script that produced the
                reported precision and recall. Re-run it and check the numbers yourself.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- cta */}
      <section className="bg-white py-14">
        <div className="mx-auto max-w-3xl px-5 text-center">
          <h2 className="text-[26px] font-semibold tracking-[-0.02em] text-navy-900">
            Compare two documents in under a minute
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-[13.5px] leading-relaxed text-navy-500">
            Upload a submission and a source. VeriText AI returns classified matches, matched-passage
            coverage, an explainable report and a side-by-side viewer — nothing is stored beyond what
            the analysis needs.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2.5">
            <Link to="/analysis/new" className="btn btn-primary btn-md">
              Start a new analysis
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
            <Link to="/dashboard" className="btn btn-ghost btn-md">
              View dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- footer */}
      <footer className="border-t border-navy-100 bg-[#fbfcfe]">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Logo to="/" />
            <p className="mt-2 max-w-sm text-[11.5px] leading-relaxed text-navy-400">
              Beyond Matching Words. Understanding Meaning. Built as an academic NLP project with a
              production mindset.
            </p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-[12px] text-navy-500">
            <Link to="/analysis/new" className="hover:text-navy-900">New analysis</Link>
            <Link to="/dashboard" className="hover:text-navy-900">Dashboard</Link>
            <Link to="/history" className="hover:text-navy-900">History</Link>
            <Link to="/methodology" className="hover:text-navy-900">Methodology</Link>
            <a href="/api/health" className="hover:text-navy-900">API health</a>
          </div>
        </div>
        <div className="border-t border-navy-100 px-5 py-3 text-center text-[11px] text-navy-400">
          Similarity is measured; misconduct is not. Always review flagged passages in context.
        </div>
      </footer>
    </div>
  )
}
