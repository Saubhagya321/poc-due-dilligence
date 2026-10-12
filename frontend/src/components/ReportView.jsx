import { CHECK_GROUPS, CHECK_LABELS } from '../checkGroups'
import WebResearchPanel from './WebResearchPanel'
import DocumentUploadPanel from './DocumentUploadPanel'
import UboBuilderPanel from './UboBuilderPanel'

// Checks that currently route to the manual checklist — only these get the
// web-research panel. Mirrors the server's PREFERRED_DOMAINS set.
const WEB_RESEARCHABLE_CHECKS = new Set([
  'gst', 'mca', 'sebi', 'nclt', 'epfo', 'esic', 'sfio',
  'rbi_cibil', 'nse', 'bse', 'msme_udyam',
])

const COLOR_DOT = {
  green: '#1a7f37',
  red: '#cf222e',
  amber: '#b08800',
  grey: '#8c8c8c',
}

const RECOMMENDATION_LABEL = {
  proceed: 'Proceed',
  'proceed-with-safeguards': 'Proceed with safeguards',
  decline: 'Decline',
}

function Dot({ color }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-block',
        width: 10,
        height: 10,
        borderRadius: '50%',
        background: COLOR_DOT[color] ?? COLOR_DOT.grey,
        marginRight: 8,
        flexShrink: 0,
      }}
    />
  )
}

export default function ReportView({ report, manualChecklist, onFindingLocked }) {
  const fieldsByCheck = Object.fromEntries(report.fields.map((f) => [f.check, f]))
  const manualByCheck = Object.fromEntries((manualChecklist ?? []).map((t) => [t.check, t]))

  return (
    <div className="card">
      <div className="report-header">
        <h2>Report — {report.vendor_id}</h2>
        <span className={`recommendation recommendation-${report.recommendation}`}>
          {RECOMMENDATION_LABEL[report.recommendation] ?? report.recommendation}
        </span>
      </div>
      <p className="muted">Score: {report.score.toFixed(1)} / 100</p>

      {report.score_reasons && report.score_reasons.length > 0 && (
        <details className="score-reasons">
          <summary>
            Why this score ({report.score_reasons.length} factor
            {report.score_reasons.length === 1 ? '' : 's'})
          </summary>
          <ul>
            {report.score_reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </details>
      )}

      {CHECK_GROUPS.map((group) => (
        <section key={group.label} className="check-group">
          <h3>{group.label}</h3>
          <ul className="report-list">
            {group.checks.map((checkKey) => {
              const field = fieldsByCheck[checkKey]
              if (!field) return null
              const manualTask = manualByCheck[checkKey]
              return (
                <li key={checkKey} className="report-row">
                  <div className="report-row-main">
                    <Dot color={field.color} />
                    <span className="check-name">{CHECK_LABELS[checkKey] ?? checkKey}</span>
                  </div>
                  <p className="report-reason">{field.reason}</p>
                  {field.source_name && (
                    <p className="report-source">
                      Source: {field.source_name}
                      {field.citation_url && (
                        <>
                          {' — '}
                          <a href={field.citation_url} target="_blank" rel="noreferrer">
                            view citation
                          </a>
                        </>
                      )}
                    </p>
                  )}
                  {field.supporting_citations && field.supporting_citations.length > 0 && (
                    <details className="supporting-citations">
                      <summary>
                        {field.supporting_citations.length} same-name match
                        {field.supporting_citations.length === 1 ? '' : 'es'} to review
                      </summary>
                      <ul>
                        {field.supporting_citations.map((c, i) => (
                          <li key={i}>
                            <a href={c.url} target="_blank" rel="noreferrer">
                              {c.title}
                            </a>{' '}
                            <span className="muted">({c.source})</span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {manualTask && (
                    <p className="report-manual">
                      Manual check: {manualTask.instruction}{' '}
                      {manualTask.portal_hint.startsWith('http') ? (
                        <a href={manualTask.portal_hint} target="_blank" rel="noreferrer">
                          open portal
                        </a>
                      ) : (
                        <span className="muted">({manualTask.portal_hint})</span>
                      )}
                    </p>
                  )}
                  {WEB_RESEARCHABLE_CHECKS.has(checkKey) && field.applicable && field.selected && (
                    <div className="analyst-tools-row">
                      <WebResearchPanel
                        vendorId={report.vendor_id}
                        check={checkKey}
                        checkLabel={CHECK_LABELS[checkKey] ?? checkKey}
                        onFindingLocked={onFindingLocked}
                      />
                      {manualTask && (
                        <DocumentUploadPanel
                          vendorId={report.vendor_id}
                          check={checkKey}
                          checkLabel={CHECK_LABELS[checkKey] ?? checkKey}
                          onFindingLocked={onFindingLocked}
                        />
                      )}
                    </div>
                  )}
                  {checkKey === 'ubo_trace' && field.applicable && field.selected && (
                    <div className="analyst-tools-row">
                      <UboBuilderPanel
                        vendorId={report.vendor_id}
                        onFindingLocked={onFindingLocked}
                      />
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
