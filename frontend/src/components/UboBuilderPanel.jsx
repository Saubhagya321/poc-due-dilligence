import { useState } from 'react'
import { uboExtract, uboLock } from '../api'
import UboGraphView from './UboGraphView'

export default function UboBuilderPanel({ vendorId, onFindingLocked }) {
  const [open, setOpen] = useState(false)
  const [files, setFiles] = useState([])
  const [analystText, setAnalystText] = useState('')
  const [graph, setGraph] = useState(null)
  const [analystNotes, setAnalystNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [locked, setLocked] = useState(false)

  async function handleExtract() {
    if (files.length === 0 && !analystText.trim()) {
      setError('Upload at least one filing or type an ownership description.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const g = await uboExtract(vendorId, files, analystText)
      setGraph(g)
      setAnalystNotes(g.analyst_notes || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleLock() {
    if (!graph) return
    setLoading(true)
    setError(null)
    try {
      await uboLock(vendorId, { ...graph, analyst_notes: analystNotes })
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
        title="Build the vendor's beneficial-ownership graph from uploaded filings or a typed description. Natural-person shareholders are auto-screened against sanctions."
      >
        Build UBO graph
      </button>
    )
  }

  return (
    <div className="document-panel">
      <div className="document-panel-header">
        <strong>UBO builder</strong>
        <button type="button" className="research-close" onClick={() => setOpen(false)}>
          ×
        </button>
      </div>

      <p
        className="document-warning"
        title="You are responsible for verifying the ownership information. The model only parses what you upload or type."
      >
        ⚠ The model only reads what you provide. Verify the extracted graph against the source
        documents before locking. Natural-person UBOs are auto-screened against sanctions.
      </p>

      {!graph && (
        <>
          <label className="ubo-upload-label">
            <strong>Upload shareholding filings</strong> (MGT-7, shareholding pattern — multiple PDFs allowed)
            <input
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.docx"
              onChange={(e) => {
                const picked = Array.from(e.target.files || [])
                setFiles((prev) => {
                  const names = new Set(prev.map((f) => f.name + ':' + f.size))
                  return [...prev, ...picked.filter((f) => !names.has(f.name + ':' + f.size))]
                })
                e.target.value = ''
              }}
            />
          </label>
          {files.length > 0 && (
            <ul className="ubo-file-list">
              {files.map((f, i) => (
                <li key={f.name + i}>
                  <span>{f.name}</span>
                  <button
                    type="button"
                    className="ubo-file-remove"
                    onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                    title="Remove this file"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <label className="ubo-upload-label">
            <strong>Or describe the ownership structure</strong>
            <textarea
              className="research-draft"
              rows={5}
              value={analystText}
              onChange={(e) => setAnalystText(e.target.value)}
              placeholder="e.g. Vendor is 60% owned by Acme Holdings Pte Ltd (Singapore), 40% by Mr. Rajesh Shah (India). Acme Holdings Pte Ltd is 100% owned by Mr. John Doe (Singapore)."
            />
          </label>
          <button
            type="button"
            className="research-generate"
            onClick={handleExtract}
            disabled={loading}
          >
            {loading ? 'Extracting…' : 'Build ownership graph'}
          </button>
        </>
      )}

      {error && <p className="research-error">⚠ {error}</p>}

      {graph && (
        <>
          <h4 style={{ margin: '12px 0 6px' }}>Ownership graph</h4>
          <UboGraphView root={graph.vendor_root} />
          <label style={{ display: 'block', marginTop: 10 }}>
            <strong>Analyst notes</strong>
            <textarea
              className="research-draft"
              rows={3}
              value={analystNotes}
              onChange={(e) => setAnalystNotes(e.target.value)}
              placeholder="Add any clarifications before locking."
            />
          </label>
          <div className="research-lock-row">
            <button
              type="button"
              className="research-generate"
              onClick={() => {
                setGraph(null)
                setFiles([])
                setAnalystText('')
              }}
              disabled={loading || locked}
            >
              Rebuild
            </button>
            <button
              type="button"
              className="research-lock"
              onClick={handleLock}
              disabled={locked || loading}
            >
              {locked ? '✓ Locked as finding' : 'Lock as finding'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
