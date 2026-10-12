import { useState } from 'react'
import { searchWebForCheck, summarizeWebHits, submitManualFinding } from '../api'

const MAX_SELECTABLE = 5

const TAG_OPTIONS = [
  { value: 'resolved-clean', label: 'Clean (green)' },
  { value: 'unresolved', label: 'Unresolved — needs human review (amber)' },
  { value: 'resolved-red-flag', label: 'Red flag (red)' },
]

export default function WebResearchPanel({ vendorId, check, checkLabel, onFindingLocked }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hits, setHits] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [draft, setDraft] = useState('')
  const [tag, setTag] = useState('unresolved')
  const [locked, setLocked] = useState(false)

  async function handleOpen() {
    setOpen(true)
    if (hits.length > 0) return
    setLoading(true)
    setError(null)
    try {
      const results = await searchWebForCheck(vendorId, check)
      setHits(results)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function toggleHit(url) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(url)) {
        next.delete(url)
      } else if (next.size < MAX_SELECTABLE) {
        next.add(url)
      }
      return next
    })
  }

  async function handleGenerateSummary() {
    const picks = hits.filter((h) => selected.has(h.url))
    if (picks.length === 0) return
    setLoading(true)
    setError(null)
    try {
      const { draft_summary } = await summarizeWebHits(vendorId, check, picks)
      setDraft(draft_summary)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleLock() {
    const picks = hits.filter((h) => selected.has(h.url))
    if (picks.length === 0 || !draft.trim()) {
      setError('Pick at least one source and have a non-empty summary before locking.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await submitManualFinding(vendorId, {
        check,
        tag,
        summary: draft.trim(),
        citation_url: picks[0].url,
        supporting_citations: picks.map((p) => ({
          title: p.title,
          url: p.url,
          source: new URL(p.url).hostname,
        })),
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
      <button type="button" className="research-trigger" onClick={handleOpen}>
        Research with web search
      </button>
    )
  }

  return (
    <div className="research-panel">
      <div className="research-panel-header">
        <strong>Web research — {checkLabel}</strong>
        <button type="button" className="research-close" onClick={() => setOpen(false)}>
          ×
        </button>
      </div>

      {error && <p className="research-error">⚠ {error}</p>}

      {loading && hits.length === 0 && <p className="muted">Searching...</p>}

      {!loading && hits.length === 0 && !error && (
        <p className="research-empty">
          No vendor-specific mentions found in authoritative sources for this check. For a clean
          vendor this is expected; for a non-trivial one, use the <strong>Upload supporting
          document</strong> panel instead, or submit a manual finding.
        </p>
      )}

      {hits.length > 0 && (
        <>
          <p className="research-hint">
            Pick up to {MAX_SELECTABLE} sources ({selected.size}/{MAX_SELECTABLE} selected). The
            summary below is drafted from these.
          </p>
          <ul className="research-hits">
            {hits.map((h) => {
              const picked = selected.has(h.url)
              const disabled = !picked && selected.size >= MAX_SELECTABLE
              return (
                <li key={h.url} className={`research-hit ${picked ? 'picked' : ''}`}>
                  <label>
                    <input
                      type="checkbox"
                      checked={picked}
                      disabled={disabled}
                      onChange={() => toggleHit(h.url)}
                    />
                    <div className="research-hit-body">
                      <a href={h.url} target="_blank" rel="noreferrer" className="research-hit-title">
                        {h.title || h.url}
                      </a>
                      {h.preview ? (
                        <p className="research-hit-preview">{h.preview}</p>
                      ) : (
                        <p className="research-hit-snippet">{h.snippet}</p>
                      )}
                      <p className="research-hit-url">{h.url}</p>
                    </div>
                  </label>
                </li>
              )
            })}
          </ul>

          <button
            type="button"
            className="research-generate"
            onClick={handleGenerateSummary}
            disabled={selected.size === 0 || loading}
          >
            {loading ? 'Generating…' : 'Generate summary from selected'}
          </button>

          {(draft || loading) && (
            <>
              <p
                className="research-warning"
                title="This summary is drafted from the sources you selected. You own the final text."
              >
                ⚠ Based on web search. False positives possible. Confirm each source yourself —
                you are the authentication authority on this finding.
              </p>
              <textarea
                className="research-draft"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={5}
                placeholder="Summary draft will appear here. Edit freely before locking."
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
        </>
      )}
    </div>
  )
}
