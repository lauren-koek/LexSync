import { useEffect, useState } from 'react'
import { fetchDocuments, fetchUpdates } from '../api.js'

// Owns the shared regulatory-document dataset consumed by the Dashboard and
// Regulatory Changes screens. Loads saved documents on mount and exposes a
// fetch/refresh action against the MAS updates endpoint.
export default function useDocuments() {
  const [days, setDays] = useState(7)
  const [docs, setDocs] = useState([])
  const [initialLoading, setInitialLoading] = useState(true)
  const [initialError, setInitialError] = useState(null)
  const [scrapeLoading, setScrapeLoading] = useState(false)
  const [scrapeError, setScrapeError] = useState(null)
  const [resultSource, setResultSource] = useState('saved')

  useEffect(() => {
    let active = true
    fetchDocuments()
      .then(results => {
        if (!active) return
        setDocs(results)
      })
      .catch(err => active && setInitialError(err.message))
      .finally(() => active && setInitialLoading(false))
    return () => {
      active = false
    }
  }, [])

  async function runFetch({ refresh = false } = {}) {
    setScrapeLoading(true)
    setScrapeError(null)
    try {
      const results = await fetchUpdates(days, { refresh })
      setDocs(results)
      setResultSource('scrape')
      return results
    } catch (err) {
      setScrapeError(err.message)
      throw err
    } finally {
      setScrapeLoading(false)
    }
  }

  return {
    days,
    setDays,
    docs,
    initialLoading,
    initialError,
    scrapeLoading,
    scrapeError,
    resultSource,
    loading: initialLoading || scrapeLoading,
    runFetch,
  }
}
