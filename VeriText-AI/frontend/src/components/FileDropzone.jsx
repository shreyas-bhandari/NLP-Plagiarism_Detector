import { useRef, useState } from 'react'
import {
  CheckCircle2,
  FileText,
  FileUp,
  RotateCcw,
  Trash2,
  TriangleAlert,
} from 'lucide-react'
import { formatBytes, number } from '../utils/format'
import { Callout, Spinner } from './Primitives'

const ACCEPTED = ['.pdf', '.docx', '.txt', '.md']

/**
 * Upload card for one document.
 *
 * Client-side validation mirrors the server rules (extension + size) so users get
 * instant feedback, but the server remains the authority — it repeats every check.
 */
export default function FileDropzone({
  label,
  description,
  file,
  document,
  uploading = false,
  progress = 0,
  error = null,
  maxMb = 25,
  disabled = false,
  onSelect,
  onRemove,
  onRetry,
}) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState(null)
  const [showPreview, setShowPreview] = useState(false)

  const pick = (candidate) => {
    setLocalError(null)
    if (!candidate) return
    const extension = `.${candidate.name.split('.').pop().toLowerCase()}`
    if (!ACCEPTED.includes(extension)) {
      setLocalError(`Unsupported file type ${extension}. Upload a PDF or DOCX document.`)
      return
    }
    if (candidate.size > maxMb * 1024 * 1024) {
      setLocalError(`That file is ${formatBytes(candidate.size)}. The limit is ${maxMb} MB.`)
      return
    }
    if (candidate.size === 0) {
      setLocalError('The selected file is empty.')
      return
    }
    onSelect(candidate)
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setDragging(false)
    if (disabled || uploading) return
    pick(event.dataTransfer.files?.[0])
  }

  const message = localError || error
  const uploaded = Boolean(document)
  const fileName = document?.filename || file?.name

  return (
    <div className="card flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-navy-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className={`flex h-6 w-6 items-center justify-center rounded-md text-[11px] font-bold ${
              uploaded ? 'bg-emerald-50 text-emerald-600' : 'bg-navy-50 text-navy-500'
            }`}
          >
            {label}
          </span>
          <div>
            <p className="text-[13px] font-semibold text-navy-900">Document {label}</p>
            <p className="text-[11.5px] text-navy-500">{description}</p>
          </div>
        </div>
        {uploaded && (
          <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            Parsed
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col p-4">
        {!file && !uploaded && (
          <div
            onDragOver={(event) => {
              event.preventDefault()
              if (!disabled) setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed px-4 py-8 text-center transition-colors ${
              dragging
                ? 'border-accent-400 bg-accent-50/60'
                : 'border-navy-200 bg-navy-50/40 hover:border-navy-300'
            } ${disabled ? 'opacity-60' : ''}`}
          >
            <span className="mb-2.5 flex h-10 w-10 items-center justify-center rounded-full bg-white text-navy-400 shadow-card">
              <FileUp className="h-4.5 w-4.5" aria-hidden="true" />
            </span>
            <p className="text-[13px] font-medium text-navy-800">
              Drop a file here, or{' '}
              <button
                type="button"
                className="link"
                onClick={() => inputRef.current?.click()}
                disabled={disabled}
              >
                browse
              </button>
            </p>
            <p className="mt-1 text-[11.5px] text-navy-500">
              PDF or DOCX · up to {maxMb} MB · text is deleted after analysis
            </p>
          </div>
        )}

        {(file || uploaded) && (
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-navy-50 text-navy-500">
              <FileText className="h-4 w-4" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-navy-900" title={fileName}>
                {fileName}
              </p>
              <p className="mt-0.5 text-[11.5px] text-navy-500">
                {uploaded
                  ? `${number(document.word_count)} words · ${number(document.sentence_count)} sentences${
                      document.page_count ? ` · ${document.page_count} pages` : ''
                    }`
                  : `${formatBytes(file.size)} · ready to upload`}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {uploaded && document.preview?.excerpt && (
                <button
                  type="button"
                  className="btn btn-quiet btn-sm"
                  onClick={() => setShowPreview((value) => !value)}
                >
                  {showPreview ? 'Hide' : 'Preview'}
                </button>
              )}
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={onRemove}
                disabled={uploading}
                aria-label={`Remove document ${label}`}
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {uploading && (
          <div className="mt-3">
            <div className="flex items-center gap-2 text-[11.5px] font-medium text-navy-600">
              <Spinner className="h-3.5 w-3.5" />
              Extracting text and segmenting sentences…
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-navy-100">
              <div
                className="h-full rounded-full bg-accent-500 transition-[width] duration-200"
                style={{ width: `${Math.max(8, progress)}%` }}
              />
            </div>
          </div>
        )}

        {showPreview && document?.preview?.excerpt && (
          <div className="mt-3 max-h-40 overflow-y-auto scroll-thin rounded-md border border-navy-100 bg-navy-50/50 p-2.5">
            <p className="snippet whitespace-pre-line">{document.preview.excerpt}</p>
          </div>
        )}

        {message && (
          <div className="mt-3">
            <Callout tone="error" className="py-2.5">
              <span className="flex items-start justify-between gap-2">
                <span>{message}</span>
                {onRetry && (
                  <button type="button" className="link shrink-0 text-[11.5px]" onClick={onRetry}>
                    <RotateCcw className="mr-1 inline h-3 w-3" />
                    Retry
                  </button>
                )}
              </span>
            </Callout>
          </div>
        )}

        {uploaded && (document.warnings || []).length > 0 && (
          <div className="mt-3 space-y-1">
            {document.warnings.slice(0, 2).map((warning) => (
              <p key={warning} className="flex items-start gap-1.5 text-[11px] leading-snug text-amber-700">
                <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                {warning}
              </p>
            ))}
          </div>
        )}

        {!file && !uploaded && (
          <div className="mt-3 flex items-center justify-between gap-2">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => inputRef.current?.click()}
              disabled={disabled}
            >
              Choose file
            </button>
            <span className="text-[11px] text-navy-400">Never shared · not used for training</span>
          </div>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(',')}
        className="hidden"
        onChange={(event) => {
          pick(event.target.files?.[0])
          event.target.value = ''
        }}
      />
    </div>
  )
}
