import { CHECK_GROUPS, CHECK_LABELS } from '../checkGroups'

export default function CheckRouting({ fields, deselected, onToggle, onRun, running, error }) {
  const fieldsByCheck = Object.fromEntries(fields.map((f) => [f.check, f]))

  return (
    <div className="card">
      <h2>Check routing</h2>
      <p className="muted">
        Every applicable check is selected by default. Turn off anything you don't want run for
        this vendor, then start screening.
      </p>

      {CHECK_GROUPS.map((group) => (
        <section key={group.label} className="check-group">
          <h3>{group.label}</h3>
          <ul className="check-list">
            {group.checks.map((checkKey) => {
              const field = fieldsByCheck[checkKey]
              if (!field) return null
              const isDeselected = deselected.has(checkKey)
              return (
                <li key={checkKey} className={`check-row ${field.applicable ? '' : 'not-applicable'}`}>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={field.applicable && !isDeselected}
                      disabled={!field.applicable}
                      onChange={() => onToggle(checkKey)}
                    />
                    <span className="check-name">{CHECK_LABELS[checkKey] ?? checkKey}</span>
                  </label>
                  <span className="check-reason">{field.reason}</span>
                </li>
              )
            })}
          </ul>
        </section>
      ))}

      {error && <p className="error">{error}</p>}

      <button type="button" className="primary" onClick={onRun} disabled={running}>
        {running ? 'Running screening…' : 'Run screening'}
      </button>
    </div>
  )
}
