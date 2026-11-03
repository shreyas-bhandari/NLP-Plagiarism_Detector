import { useCallback, useRef, useState } from 'react'
import { Upload } from 'lucide-react'

export default function DropZone({ onFiles, accept, className = '' }) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  const prevent = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDragOver = useCallback((e) => { prevent(e); setIsDragging(true) }, [])
  const handleDragLeave = useCallback((e) => { prevent(e); setIsDragging(false) }, [])
  const handleDrop = useCallback(
    (e) => {
      prevent(e)
      setIsDragging(false)
      const files = Array.from((e.dataTransfer || {}).files || [])
        .filter((f) => f.type === '' || accept.split(',').some((ext) => f.name.toLowerCase().endsWith(ext.trim())))
      if (files.length) onFiles(files)
    },
    [accept, onFiles],
  )

  const openBrowser = () => inputRef.current && inputRef.current.click()

  const handleInputChange = (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length) onFiles(files)
  }

  return (
    <div
      className={`drop-zone ${className} ${isDragging ? 'drag-active' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={openBrowser}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && openBrowser()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={false}
        style={{ display: 'none' }}
        onChange={handleInputChange}
      />
      <Upload className="w-6 h-6 text-primary-dark" />
      <p className="font-medium text-ink">Drop a file here or browse</p>
      <p className="drop-hint">PDF / DOCX · Up to 25 MB</p>
    </div>
  )
}
