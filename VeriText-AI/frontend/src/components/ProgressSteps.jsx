import { Check, Loader2 } from 'lucide-react'

/**
 * Processing indicator for the synchronous compare request.
 *
 * The backend returns one response, so the stages are driven by real client
 * state (files parsed, request in flight) plus an elapsed timer — no fake
 * percentages or invented progress.
 */
export default function ProgressSteps({ steps, elapsedMs }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-semibold text-navy-900">Running semantic analysis</p>
        <span className="tnum text-[12px] font-medium text-navy-500">
          {(elapsedMs / 1000).toFixed(1)}s
        </span>
      </div>
      <ol className="mt-3 space-y-2.5">
        {steps.map((step) => (
          <li key={step.key} className="flex items-start gap-2.5">
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
              {step.status === 'done' && (
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-white">
                  <Check className="h-2.5 w-2.5" strokeWidth={3} aria-hidden="true" />
                </span>
              )}
              {step.status === 'active' && (
                <Loader2 className="h-4 w-4 animate-spin text-accent-500" aria-hidden="true" />
              )}
              {step.status === 'pending' && (
                <span className="h-2 w-2 rounded-full bg-navy-200" aria-hidden="true" />
              )}
            </span>
            <div>
              <p
                className={`text-[12.5px] font-medium ${
                  step.status === 'pending' ? 'text-navy-400' : 'text-navy-800'
                }`}
              >
                {step.label}
              </p>
              {step.detail && step.status !== 'pending' && (
                <p className="text-[11.5px] text-navy-500">{step.detail}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-3 border-t border-navy-100 pt-2.5 text-[11px] leading-snug text-navy-400">
        Sentences are encoded by the pretrained MiniLM transformer on the server, then compared
        with cosine similarity and lexical evidence. Larger documents take longer.
      </p>
    </div>
  )
}
