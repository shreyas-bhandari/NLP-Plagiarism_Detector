import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeftRight,
  ChevronDown,
  Info,
  Lock,
  Play,
  Settings2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import FileDropzone from '../components/FileDropzone'
import ProgressSteps from '../components/ProgressSteps'
import { Callout } from '../components/Primitives'
import { useToast } from '../components/Toast'
import { useRequest } from '../hooks/useRequest'
import { compareDocuments, deleteDocument, getHealth, uploadDocument } from '../services/api'

const DEFAULT_OPTIONS = {
  exclude_references: true,
  exclude_headings: true,
  ignore_quotations: false,
  semantic_threshold: 0.62,
}

const EMPTY_SLOT = { file: null, document: null, uploading: false, progress: 0, error: null }

export default function NewAnalysis() {
  const navigate = useNavigate()
  const toast = useToast()
  const health = useRequest(() => getHealth(), [])
  const maxMb = health.data?.limits?.max_upload_mb || 25

  const [slots, setSlots] = useState({ A: { ...EMPTY_SLOT }, B: { ...EMPTY_SLOT } })
  const [options, setOptions] = useState(DEFAULT_OPTIONS)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const startedAt = useRef(0)
  const timer = useRef(null)

  useEffect(() => () => window.clearInterval(timer.current), [])

  const updateSlot = (label, patch) =>
    setSlots((current) => ({ ...current, [label]: { ...current[label], ...patch } }))

  const handleSelect = async (label, file) => {
    updateSlot(label, { file, document: null, uploading: true, progress: 0, error: null })
    try {
      const document = await uploadDocument(file, label, (progress) =>
        updateSlot(label, { progress }),
      )
      updateSlot(label, { document, uploading: false, progress: 100 })
      if (document.warnings?.length) {
        toast.info(`Document ${label} parsed with notes`, { detail: document.warnings[0] })
      }
    } catch (error) {
      updateSlot(label, { uploading: false, error: error.message, progress: 0 })
    }
  }

  const handleRemove = async (label) => {
    const current = slots[label]
    setSlots((state) => ({ ...state, [label]: { ...EMPTY_SLOT } }))
    if (current.document?.document_id) {
      try {
        await deleteDocument(current.document.document_id)
      } catch {
        /* the server purges expired uploads anyway */
      }
    }
  }

  const handleSwap = () => setSlots((current) => ({ A: current.B, B: current.A }))

  const ready = Boolean(slots.A.document && slots.B.document)
  const busy = slots.A.uploading || slots.B.uploading || running

  const startAnalysis = async () => {
    if (!ready || running) return
    setRunning(true)
    setRunError(null)
    setElapsed(0)
    startedAt.current = Date.now()
    timer.current = window.setInterval(
      () => setElapsed(Date.now() - startedAt.current),
      120,
    )
    try {
      const result = await compareDocuments({
        docAId: slots.A.document.document_id,
        docBId: slots.B.document.document_id,
        options,
      })
      window.clearInterval(timer.current)
      toast.success('Analysis complete', {
        detail: `${result.summary.primary_matches} primary matches found`,
      })
      navigate(`/analysis/${result.analysis_id}`, { state: { fresh: true } })
    } catch (error) {
      window.clearInterval(timer.current)
      setRunError(error)
      setRunning(false)
    }
  }

  const steps = useMemo(
    () => [
      {
        key: 'parse',
        label: 'Extract text and segment sentences',
        status: ready && !running ? 'done' : slots.A.document || slots.B.document ? 'active' : 'pending',
        detail: ready
          ? `${slots.A.document.sentence_count} + ${slots.B.document.sentence_count} sentences ready`
          : 'Upload both documents',
      },
      {
        key: 'embed',
        label: 'Encode sentences and compute cosine similarity',
        status: running ? 'active' : ready ? 'pending' : 'pending',
        detail: running ? 'MiniLM transformer, batched on the server' : '',
      },
      {
        key: 'report',
        label: 'Classify matches and prepare the review view',
        status: 'pending',
        detail: '',
      },
    ],
    [ready, running, slots.A.document, slots.B.document],
  )

  return (
    <div className="mx-auto max-w-[1180px]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-[-0.02em] text-navy-900">New analysis</h1>
          <p className="mt-0.5 text-[13px] text-navy-500">
            Compare a submitted document against a source to find copied, edited and paraphrased
            passages.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-[11.5px] text-navy-400">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />
          Files are parsed in a temp file and deleted immediately
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.6fr_1fr] lg:items-start">
        {/* ------------------------------------------------------- uploads */}
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <FileDropzone
              label="A"
              description="The document under review"
              file={slots.A.file}
              document={slots.A.document}
              uploading={slots.A.uploading}
              progress={slots.A.progress}
              error={slots.A.error}
              maxMb={maxMb}
              disabled={busy}
              onSelect={(file) => handleSelect('A', file)}
              onRemove={() => handleRemove('A')}
              onRetry={() => handleSelect('A', slots.A.file)}
            />
            <FileDropzone
              label="B"
              description="The comparison source"
              file={slots.B.file}
              document={slots.B.document}
              uploading={slots.B.uploading}
              progress={slots.B.progress}
              error={slots.B.error}
              maxMb={maxMb}
              disabled={busy}
              onSelect={(file) => handleSelect('B', file)}
              onRemove={() => handleRemove('B')}
              onRetry={() => handleSelect('B', slots.B.file)}
            />
          </div>

          <div className="flex items-center justify-center">
            <button
              type="button"
              onClick={handleSwap}
              className="btn btn-ghost btn-sm"
              disabled={busy || (!slots.A.document && !slots.B.document)}
            >
              <ArrowLeftRight className="h-3.5 w-3.5" aria-hidden="true" />
              Swap A / B
            </button>
          </div>

          {/* ------------------------------------------------------ options */}
          <div className="card">
            <div className="card-header">
              <div>
                <p className="text-[13px] font-semibold text-navy-900">Matching settings</p>
                <p className="mt-0.5 text-[11.5px] text-navy-500">
                  Applied to both documents before comparison
                </p>
              </div>
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => setShowAdvanced((value) => !value)}
                aria-expanded={showAdvanced}
              >
                <Settings2 className="h-3.5 w-3.5" aria-hidden="true" />
                Advanced
                <ChevronDown className={`h-3 w-3 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
              </button>
            </div>
            <div className="space-y-2.5 p-4">
              {[
                {
                  key: 'exclude_references',
                  label: 'Exclude reference lists and bibliographies',
                  hint: 'Bibliographies repeat across papers and inflate similarity without indicating reuse.',
                },
                {
                  key: 'exclude_headings',
                  label: 'Exclude headings and section titles',
                  hint: 'Short structural lines are not comparable content.',
                },
                {
                  key: 'ignore_quotations',
                  label: 'Ignore quoted sentences',
                  hint: 'Useful when the document legitimately quotes sources at length.',
                },
              ].map((item) => (
                <label
                  key={item.key}
                  className="flex cursor-pointer items-start gap-2.5 rounded-md border border-navy-100 p-2.5 hover:bg-navy-50/40"
                >
                  <input
                    type="checkbox"
                    checked={options[item.key]}
                    onChange={(event) =>
                      setOptions((current) => ({ ...current, [item.key]: event.target.checked }))
                    }
                    className="mt-0.5 h-3.5 w-3.5 rounded border-navy-300 text-accent-600 focus:ring-accent-300"
                  />
                  <span>
                    <span className="block text-[12.5px] font-medium text-navy-800">{item.label}</span>
                    <span className="mt-0.5 block text-[11px] leading-snug text-navy-500">{item.hint}</span>
                  </span>
                </label>
              ))}

              {showAdvanced && (
                <div className="rounded-md border border-navy-100 bg-navy-50/40 p-3">
                  <div className="flex items-center justify-between">
                    <label htmlFor="threshold" className="text-[12.5px] font-medium text-navy-800">
                      Semantic flag threshold
                    </label>
                    <span className="tnum text-[12px] font-semibold text-navy-900">
                      {options.semantic_threshold.toFixed(2)}
                    </span>
                  </div>
                  <input
                    id="threshold"
                    type="range"
                    min="0.45"
                    max="0.85"
                    step="0.01"
                    value={options.semantic_threshold}
                    onChange={(event) =>
                      setOptions((current) => ({
                        ...current,
                        semantic_threshold: Number(event.target.value),
                      }))
                    }
                    className="mt-2 w-full accent-accent-600"
                  />
                  <p className="mt-1.5 text-[11px] leading-snug text-navy-500">
                    Cosine similarity a pair must reach to be reported as a semantic match. Higher
                    values reduce noise and miss more paraphrase; lower values find more rewritten
                    text and flag more standard phrasing. The default (0.62) comes from the
                    project&apos;s labelled evaluation.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* -------------------------------------------------------- action */}
        <div className="space-y-3 lg:sticky lg:top-[4.5rem]">
          <div className="card p-4">
            <p className="text-[13px] font-semibold text-navy-900">Run comparison</p>
            <ul className="mt-2.5 space-y-1.5">
              {[
                { label: 'Document A', value: slots.A.document?.filename },
                { label: 'Document B', value: slots.B.document?.filename },
              ].map((row) => (
                <li key={row.label} className="flex items-baseline justify-between gap-3">
                  <span className="text-[11.5px] text-navy-500">{row.label}</span>
                  <span
                    className={`truncate text-[11.5px] font-medium ${
                      row.value ? 'text-navy-800' : 'text-navy-300'
                    }`}
                    title={row.value || ''}
                  >
                    {row.value || 'not uploaded'}
                  </span>
                </li>
              ))}
            </ul>

            <button
              type="button"
              className="btn btn-primary btn-md mt-3.5 w-full"
              onClick={startAnalysis}
              disabled={!ready || busy}
            >
              {running ? (
                <>
                  <Sparkles className="h-3.5 w-3.5 animate-pulse" aria-hidden="true" />
                  Analysing…
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" aria-hidden="true" />
                  Run semantic analysis
                </>
              )}
            </button>
            {!ready && !busy && (
              <p className="mt-2 text-center text-[11px] text-navy-400">
                Upload both documents to enable the analysis
              </p>
            )}

            {runError && (
              <div className="mt-3">
                <Callout tone="error" title="Analysis failed">
                  {runError.message}
                  {runError.hint ? <span className="block mt-1">{runError.hint}</span> : null}
                </Callout>
              </div>
            )}
          </div>

          {(running || (ready && !runError)) && (
            <ProgressSteps
              steps={
                running
                  ? steps.map((step) =>
                      step.key === 'embed' ? { ...step, status: 'active' } : step,
                    )
                  : steps
              }
              elapsedMs={running ? elapsed : 0}
            />
          )}

          <div className="card p-4">
            <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-navy-900">
              <Lock className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
              Privacy during analysis
            </p>
            <ul className="mt-2 space-y-1.5 text-[11.5px] leading-relaxed text-navy-500">
              <li>• Uploads are written to a private temp file and deleted right after text extraction.</li>
              <li>• Extracted text is held only for the viewer and expires automatically.</li>
              <li>• Results keep scores and short snippets — never the full document.</li>
              <li>• Deleting an analysis removes its stored text immediately.</li>
            </ul>
          </div>

          <Callout tone="info" title="What you will get">
            Classified matches (exact / near-exact / semantic), coverage metrics, similarity
            distribution, a side-by-side highlighting viewer and a downloadable PDF report.
          </Callout>

          {health.data && (
            <div className="flex items-start gap-2 rounded-lg border border-navy-100 bg-white px-3 py-2.5">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-navy-400" aria-hidden="true" />
              <p className="text-[11px] leading-snug text-navy-500">
                Engine: <span className="font-mono">{health.data.model.model}</span> ·{' '}
                {health.data.model.dimension}-dimensional embeddings · max {maxMb} MB per file.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
