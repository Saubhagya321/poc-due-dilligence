import { useState } from 'react'
import IntakeForm from './components/IntakeForm'
import CheckRouting from './components/CheckRouting'
import ReportView from './components/ReportView'
import { intakeVendor, overrideChecks, runScreening, getManualChecklist } from './api'
import './App.css'

const STEPS = { INTAKE: 'intake', CHECKS: 'checks', REPORT: 'report' }

function App() {
  const [step, setStep] = useState(STEPS.INTAKE)
  const [vendorId, setVendorId] = useState(null)
  const [fields, setFields] = useState([])
  const [deselected, setDeselected] = useState(new Set())
  const [report, setReport] = useState(null)
  const [manualChecklist, setManualChecklist] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleIntake(payload) {
    setBusy(true)
    setError(null)
    try {
      const result = await intakeVendor(payload)
      setVendorId(result.vendor_id)
      setFields(result.fields)
      setDeselected(new Set())
      setStep(STEPS.CHECKS)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function toggleCheck(checkKey) {
    setDeselected((prev) => {
      const next = new Set(prev)
      if (next.has(checkKey)) {
        next.delete(checkKey)
      } else {
        next.add(checkKey)
      }
      return next
    })
  }

  async function handleRun() {
    setBusy(true)
    setError(null)
    try {
      if (deselected.size > 0) {
        const overridden = await overrideChecks(vendorId, Array.from(deselected))
        setFields(overridden.fields)
      }
      const [reportResult, manualResult] = await Promise.all([
        runScreening(vendorId),
        getManualChecklist(vendorId),
      ])
      setReport(reportResult)
      setManualChecklist(manualResult)
      setStep(STEPS.REPORT)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function startOver() {
    setStep(STEPS.INTAKE)
    setVendorId(null)
    setFields([])
    setDeselected(new Set())
    setReport(null)
    setManualChecklist([])
    setError(null)
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Supplier Due-Diligence &amp; Risk Screening</h1>
        <p className="muted">21-check vendor screening — global compliance, India regulatory, litigation, ownership.</p>
      </header>

      <main>
        {step === STEPS.INTAKE && (
          <IntakeForm onSubmit={handleIntake} submitting={busy} error={error} />
        )}

        {step === STEPS.CHECKS && (
          <CheckRouting
            fields={fields}
            deselected={deselected}
            onToggle={toggleCheck}
            onRun={handleRun}
            running={busy}
            error={error}
          />
        )}

        {step === STEPS.REPORT && report && (
          <>
            <ReportView
              report={report}
              manualChecklist={manualChecklist}
              onFindingLocked={async () => {
                try {
                  const refreshed = await runScreening(vendorId)
                  setReport(refreshed)
                } catch (err) {
                  setError(err.message)
                }
              }}
            />
            <button type="button" className="secondary" onClick={startOver}>
              Screen another vendor
            </button>
          </>
        )}
      </main>
    </div>
  )
}

export default App
