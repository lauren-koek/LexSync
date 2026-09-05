async function readJson(res) {
  let payload
  try {
    payload = await res.json()
  } catch {
    throw new Error(`Server returned an invalid response (${res.status})`)
  }
  if (!res.ok) {
    const detail = typeof payload?.detail === 'string' ? payload.detail : JSON.stringify(payload)
    throw new Error(`Server error ${res.status}: ${detail}`)
  }
  return payload
}

export async function fetchDocuments() {
  return readJson(await fetch('/api/v1/documents'))
}

export async function fetchInternalDocuments(query = '') {
  const suffix = query ? `?q=${encodeURIComponent(query)}` : ''
  return readJson(await fetch(`/api/v1/internal-documents${suffix}`))
}

export async function uploadInternalDocument(file, title = '') {
  const body = new FormData()
  body.append('file', file)
  if (title.trim()) body.append('title', title.trim())
  return readJson(await fetch('/api/v1/internal-documents', { method: 'POST', body }))
}

export async function searchInternalDocuments(query, limit = 10) {
  return readJson(await fetch('/api/v1/internal-documents/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
  }))
}

export async function fetchInternalDocument(id) {
  return readJson(await fetch(`/api/v1/internal-documents/${id}`))
}

export async function fetchInternalDocumentPdfUrl(id) {
  return readJson(await fetch(`/api/v1/internal-documents/${id}/pdf-url`))
}

export async function deleteInternalDocument(id) {
  const response = await fetch(`/api/v1/internal-documents/${id}`, { method: 'DELETE' })
  if (!response.ok) return readJson(response)
}

export async function reanalyzeInternalDocument(id) {
  return readJson(await fetch(`/api/v1/internal-documents/${id}/reanalyze`, { method: 'POST' }))
}

export async function fetchRegulatorySuggestions(id) {
  return readJson(await fetch(`/api/v1/documents/${id}/suggestions`))
}

export async function updateSuggestionStatus(id, status) {
  return readJson(await fetch(`/api/v1/document-suggestions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }))
}

export async function fetchUpdates(days, { refresh = false } = {}) {
  const res = await fetch('/api/v1/updates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days, refresh }),
  })
  return readJson(res)
}

export async function runAnalysis({
  regulationText,
  internalAssetText,
  regulationFile,
  internalAssetFile,
}) {
  const body = new FormData()
  body.append('regulation_text', regulationText)
  body.append('internal_asset_text', internalAssetText)
  body.append('regulation_id', 'Uploaded_Regulation')
  body.append('asset_id', 'Uploaded_Internal_Asset')
  if (regulationFile) body.append('regulation_file', regulationFile)
  if (internalAssetFile) body.append('internal_asset_file', internalAssetFile)

  return readJson(await fetch('/api/v1/analysis/upload', { method: 'POST', body }))
}
