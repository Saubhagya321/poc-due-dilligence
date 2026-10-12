import { useState } from 'react'

const ENTITY_TYPES = [
  { value: 'sole_proprietorship', label: 'Sole Proprietorship' },
  { value: 'partnership', label: 'Partnership' },
  { value: 'llp', label: 'LLP' },
  { value: 'opc', label: 'OPC' },
  { value: 'private_limited', label: 'Private Limited' },
  { value: 'public_limited', label: 'Public Limited' },
  { value: 'huf', label: 'HUF' },
]

const EMPTY_FORM = {
  vendor_id: '',
  name: '',
  pan: '',
  entity_type: 'private_limited',
  contract_value: '',
  has_physical_premises: false,
  key_persons_text: '',
}

export default function IntakeForm({ onSubmit, submitting, error }) {
  const [form, setForm] = useState(EMPTY_FORM)

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    const payload = {
      vendor_id: form.vendor_id.trim(),
      name: form.name.trim(),
      pan: form.pan.trim().toUpperCase() || undefined,
      entity_type: form.entity_type,
      contract_value: form.contract_value,
      has_physical_premises: form.has_physical_premises,
    }
    const persons = form.key_persons_text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    if (persons.length > 0) {
      payload.key_persons = persons
    }
    onSubmit(payload)
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>Vendor intake</h2>
      <p className="muted">
        Enter the vendor's details to see which of the 21 due-diligence checks apply before
        anything runs.
      </p>

      <div className="field-grid">
        <label>
          Vendor ID
          <input
            required
            value={form.vendor_id}
            onChange={(e) => update('vendor_id', e.target.value)}
            placeholder="vendor-001"
          />
        </label>
        <label>
          Vendor name
          <input
            required
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
            placeholder="Acme Traders Pvt Ltd"
          />
        </label>
        <label>
          PAN
          <input
            required
            value={form.pan}
            onChange={(e) => update('pan', e.target.value)}
            placeholder="AAAAA9999A"
            maxLength={10}
          />
        </label>
        <label>
          Entity type
          <select value={form.entity_type} onChange={(e) => update('entity_type', e.target.value)}>
            {ENTITY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Contract value (₹)
          <input
            required
            type="number"
            min="0"
            value={form.contract_value}
            onChange={(e) => update('contract_value', e.target.value)}
            placeholder="500000"
          />
        </label>
      </div>

      <div className="field-row checkbox-row">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={form.has_physical_premises}
            onChange={(e) => update('has_physical_premises', e.target.checked)}
          />
          Has physical premises
        </label>
      </div>

      <details className="optional-fields">
        <summary>Optional context (promoters / directors)</summary>
        <div className="field-grid">
          <label>
            Key persons (directors / promoters / proprietors — comma separated)
            <input
              value={form.key_persons_text}
              onChange={(e) => update('key_persons_text', e.target.value)}
              placeholder="Mehul Choksi, Rajesh Kumar"
            />
          </label>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          Beneficial ownership is traced on the report screen via the dedicated UBO panel —
          upload the vendor's MGT-7 / shareholding filings there. Supporting documents for other
          manual checks (GST cert, CIBIL report, etc.) are also uploaded per-check.
        </p>
      </details>

      {error && <p className="error">{error}</p>}

      <button type="submit" className="primary" disabled={submitting}>
        {submitting ? 'Submitting…' : 'Route checks'}
      </button>
    </form>
  )
}
