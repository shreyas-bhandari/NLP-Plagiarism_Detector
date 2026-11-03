import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, ShieldCheck } from 'lucide-react'
import FileCard from '../components/FileCard'
import Collapsible from '../components/Collapsible'

export default function UploadPage() {
  const navigate = useNavigate()
  const [fileA, setFileA] = useState(null)
  const [fileB, setFileB] = useState(null)
  const [options, setOptions] = useState({
    excludeHeadings: true,
    ignoreQuotes: false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleAnalyze = useCallback(async (e) => {
    e.preventDefault()
    setError(null)
    if (!fileA || !fileB) {
      setError('Please upload both documents before analyzing.')
      return
    }
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('file_a', fileA)
      formData.append('file_b', fileB)

      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.error || 'Analysis failed.')
      }

      navigate(`/result/${data.analysis_id}`)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [fileA, fileB, navigate])

  return (
    <div className="max-w-4xl mx-auto px-6 py-10 lg:py-16">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-ink tracking-tight mb-2">
          Compare Two Documents
        </h1>
        <p className="text-body text-muted">
          Find copied or paraphrased content.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 p-3 rounded-lg border border-red/20 bg-red/50 text-[12px] text-red dark:text-red">
          {error}
        </div>
      )}

      {/* Upload cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <FileCard
          title="Document A"
          caption="The document under review"
          file={fileA}
          onChange={setFileA}
          onRemove={() => setFileA(null)}
        />
        <FileCard
          title="Document B"
          caption="The comparison source"
          file={fileB}
          onChange={setFileB}
          onRemove={() => setFileB(null)}
        />
      </div>

      {/* Analysis options */}
      <div className="card mb-8">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-sm font-bold text-ink">Analysis options</h3>
        </div>
        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={options.excludeHeadings}
              onChange={(e) =>
                setOptions((o) => ({ ...o, excludeHeadings: e.target.checked }))
              }
              className="rounded border-primary text-primary focus:ring-primary"
            />
            <span className="text-sm text-body">Exclude headings and section titles</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={options.ignoreQuotes}
              onChange={(e) =>
                setOptions((o) => ({ ...o, ignoreQuotes: e.target.checked }))
              }
              className="rounded border-primary text-primary focus:ring-primary"
            />
            <span className="text-sm text-body">Ignore quoted sentences</span>
          </label>
        </div>
      </div>

      {/* Privacy */}
      <div className="mb-8">
        <div className="flex items-start gap-2 mb-2">
          <ShieldCheck className="w-4 h-4 text-primary mt-0.5" />
          <p className="text-xs text-muted leading-relaxed">
            🔒 Your documents are private and deleted after processing.
          </p>
        </div>
        <Collapsible title="Privacy details">
          <p className="text-xs text-muted leading-relaxed">
            VeriText processes your documents in memory to compute similarity
            and evidence. Uploaded files are stored temporarily for the duration
            of the analysis and are removed once processing completes. Documents
            are never shared with third parties and are not used to train any
            model. For the full privacy policy, contact your administrator.
          </p>
        </Collapsible>
      </div>

      {/* Primary action */}
      <button
        onClick={handleAnalyze}
        disabled={loading || !fileA || !fileB}
        className="btn-primary w-full lg:w-auto"
      >
        {loading ? 'Analyzing…' : 'Analyze Documents'}
        <ArrowRight className="w-4 h-4 ml-2" />
      </button>
      {(!loading && !fileA && !fileB) && (
        <p className="mt-4 text-[12px] text-muted text-center">
          Supported: PDF, DOCX, TXT · Up to 25 MB per file
        </p>
      )}
    </div>
  )
}
