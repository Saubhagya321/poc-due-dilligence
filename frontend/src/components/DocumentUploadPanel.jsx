import { useState } from 'react'
import { submitManualFinding, uploadDocument } from '../api'

const TAG_OPTIONS = [
  { value: 'resolved-clean', label: 'Clean (green)' },
  { value: 'unresolved', label: 'Unresolved — needs human review (amber)' },
  { value: 'resolved-red-flag', label: 'Red flag (red)' },
]

export default function DocumentUploadPanel({ vendorId, check, checkLabel, onFindingLocked }) {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [draft, setDraft] = useState('')
  const [tag, setTag] = useState('unresolved')
  const [filename, setFilename] = useState(null)
  const [extractedPreview, setExtractedPreview] = useState('')
  const [locked, setLocked] = useState(false)

  async function handleAnalyze() {
    if (!file) {
      setError('Choose a file first.')
      return
    }
    setLoading(true)
    setError(null)
    setDraft('')
    try {
      const resp = await uploadDocument(vendorId, check, file)
      setDraft(resp.draft_summary)
      setTag(resp.draft_tag)
      setFilename(resp.filename)
      setExtractedPreview(resp.extracted_preview)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleLock() {
    if (!draft.trim()) {
      setError('Summary cannot be empty before locking.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await submitManualFinding(vendorId, {
        check,
        tag,
        summary: draft.trim(),
        citation_url: null,
        supporting_citations: filename
          ? [{ title: `Uploaded: ${filename}`, url: 'file://local-upload', source: 'analyst upload' }]
          : [],
      })
      setLocked(true)
      if (onFindingLocked) onFindingLocked()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="document-trigger"
        onClick={() => setOpen(true)}
        title="Upload a supporting document (PAN card, GST cert, CIBIL report, etc.) for AI analysis. You authenticate the document — the model only reads what you upload."
      >
        Upload supporting document
      </button>
    )
  }

  return (
    <div className="document-panel">
      <div className="document-panel-header">
        <strong>Document analysis — {checkLabel}</strong>
        <button type="button" className="research-close" onClick={() => setOpen(false)}>
          ×
        </button>
      </div>

      <p
        className="document-warning"
        title="You are responsible for the authenticity of this document. The model only reads what you upload — if the document is fake or tampered, the model's output will be wrong."
      >
        ⚠ Document authentication is on you. The model only reads what you upload. Confirm the
        document is genuine before trusting the AI's reading.
      </p>

      <div className="document-upload-row">
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.docx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          className="research-generate"
          onClick={handleAnalyze}
          disabled={!file || loading}
        >
          {loading && !draft ? 'Extracting & analysing…' : 'Analyze document'}
        </button>
      </div>

      {error && <p className="research-error">⚠ {error}</p>}

      {filename && (
        <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          Processed: <strong>{filename}</strong>
        </p>
      )}

      {extractedPreview && (
        <details className="document-extract">
          <summary>Extracted text (first 600 chars)</summary>
          <pre>{extractedPreview}</pre>
        </details>
      )}

      {(draft || loading) && (
        <>
          <textarea
            className="research-draft"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={5}
            placeholder="Model's draft will appear here. Edit before locking."
          />
          <div className="research-lock-row">
            <label>
              Tag:{' '}
              <select value={tag} onChange={(e) => setTag(e.target.value)}>
                {TAG_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="research-lock"
              onClick={handleLock}
              disabled={locked || loading || !draft.trim()}
            >
              {locked ? '✓ Locked as finding' : 'Lock as finding'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
