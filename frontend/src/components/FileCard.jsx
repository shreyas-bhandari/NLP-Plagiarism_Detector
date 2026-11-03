import { useState } from 'react'
import { FileText, X } from 'lucide-react'
import DropZone from './DropZone'

export default function FileCard({ title, caption, file, onChange, onRemove }) {
  const [dragActive, setDragActive] = useState(false)

  const accept = '.pdf, .docx, .doc, .txt'

  const handleFiles = (files) => {
    const f = files[0]
    const maxSize = 25 * 1024 * 1024
    if (f.size > maxSize) {
      alert(`File is too large. Maximum size is 25 MB.`)
      return
    }
    onChange(f)
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  return (
    <div className="card">
      <div className="flex items-start gap-2 mb-3">
        <FileText className="w-5 h-5 text-primary-dark" />
        <div>
          <h3 className="text-base font-bold text-ink leading-none">{title}</h3>
          <p className="text-xs text-muted leading-none">{caption}</p>
        </div>
      </div>

      <DropZone
        accept={accept}
        onFiles={handleFiles}
        className={dragActive ? 'drag-active' : ''}
        onDragEnter={() => setDragActive(true)}
        onDragLeave={() => setDragActive(false)}
      />

      {file && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-border bg-slate/40 p-2">
          <FileText className="w-4 h-4 text-muted" />
          <span className="text-sm text-body truncate">{file.name}</span>
          <span className="text-xs text-muted ml-auto">{formatSize(file.size)}</span>
          <button
            onClick={(e) => { e.stopPropagation(); onRemove() }}
            className="w-6 h-6 rounded hover:bg-slate/60 text-muted hover:text-ink flex items-center justify-center"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>
      )}
    </div>
  )
}
