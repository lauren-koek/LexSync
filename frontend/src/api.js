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

export async function fetchUpdates(days) {
  const res = await fetch('/api/v1/updates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days }),
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
