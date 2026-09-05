import { useCallback, useEffect, useState } from 'react'
import { deleteInternalDocument, fetchInternalDocuments, searchInternalDocuments, uploadInternalDocument } from '../api.js'

export default function useInternalDocuments() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searching, setSearching] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setDocuments(await fetchInternalDocuments()) }
    catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  async function upload(file, title) {
    setError(null)
    const result = await uploadInternalDocument(file, title)
    setDocuments(items => [result, ...items.filter(item => item.id !== result.id)])
    return result
  }

  async function search(query) {
    setSearching(true)
    setError(null)
    try { setDocuments(await searchInternalDocuments(query)) }
    catch (err) { setError(err.message); throw err }
    finally { setSearching(false) }
  }

  async function remove(id) {
    await deleteInternalDocument(id)
    setDocuments(items => items.filter(item => item.id !== id))
  }

  return { documents, loading, searching, error, upload, search, resetSearch: load, remove }
}
