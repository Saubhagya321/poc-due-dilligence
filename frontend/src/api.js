const BASE_URL = 'http://127.0.0.1:8000'

async function request(path, options) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const body = await response.json()
  if (!response.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail)
    throw new Error(detail || `Request to ${path} failed with ${response.status}`)
  }
  return body
}

export function intakeVendor(vendor) {
  return request('/vendors', { method: 'POST', body: JSON.stringify(vendor) })
}

export function overrideChecks(vendorId, deselectedChecks) {
  return request(`/vendors/${encodeURIComponent(vendorId)}/checks`, {
    method: 'PATCH',
    body: JSON.stringify({ deselected_checks: deselectedChecks }),
  })
}

export function runScreening(vendorId) {
  return request(`/vendors/${encodeURIComponent(vendorId)}/run`, { method: 'POST' })
}

export function getManualChecklist(vendorId) {
  return request(`/vendors/${encodeURIComponent(vendorId)}/manual-checklist`)
}

export function searchWebForCheck(vendorId, check) {
  return request(
    `/vendors/${encodeURIComponent(vendorId)}/web-research/${encodeURIComponent(check)}`,
  )
}

export function summarizeWebHits(vendorId, check, selectedHits) {
  return request(
    `/vendors/${encodeURIComponent(vendorId)}/web-research/${encodeURIComponent(check)}/summarize`,
    { method: 'POST', body: JSON.stringify({ selected_hits: selectedHits }) },
  )
}

export function submitManualFinding(vendorId, finding) {
  return request(
    `/vendors/${encodeURIComponent(vendorId)}/manual-findings`,
    { method: 'POST', body: JSON.stringify(finding) },
  )
}

export async function uploadDocument(vendorId, check, file) {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await fetch(
    `${BASE_URL}/vendors/${encodeURIComponent(vendorId)}/documents/${encodeURIComponent(check)}`,
    { method: 'POST', body: formData },
  )
  const body = await resp.json()
  if (!resp.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail)
    throw new Error(detail || `Upload failed with ${resp.status}`)
  }
  return body
}

export async function uboExtract(vendorId, files, analystText) {
  const formData = new FormData()
  for (const f of files) formData.append('files', f)
  formData.append('analyst_text', analystText || '')
  const resp = await fetch(
    `${BASE_URL}/vendors/${encodeURIComponent(vendorId)}/ubo/extract`,
    { method: 'POST', body: formData },
  )
  const body = await resp.json()
  if (!resp.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail)
    throw new Error(detail || `UBO extract failed with ${resp.status}`)
  }
  return body
}

export function uboLock(vendorId, graph) {
  return request(`/vendors/${encodeURIComponent(vendorId)}/ubo/lock`, {
    method: 'POST',
    body: JSON.stringify(graph),
  })
}
