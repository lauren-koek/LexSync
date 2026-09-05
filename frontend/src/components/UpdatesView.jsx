import { useEffect, useState } from 'react'
import { fetchDocuments, fetchUpdates } from '../api.js'
import DetailPanel from './DetailPanel.jsx'
import DocumentList from './DocumentList.jsx'
import TopBar from './TopBar.jsx'

export default function UpdatesView() {
  const [days, setDays] = useState(7)
  const [docs, setDocs] = useState([])
  const [selected, setSelected] = useState(null)
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
        setSelected(results[0] || null)
      })
      .catch(err => active && setInitialError(err.message))
      .finally(() => {
        if (active) {
          setInitialLoading(false)
        }
      })
    return () => { active = false }
  }, [])

  async function handleFetch() {
    setScrapeLoading(true)
    setScrapeError(null)
    try {
      const results = await fetchUpdates(days)
      setDocs(results)
      setSelected(results[0] || null)
      setResultSource('scrape')
    } catch (err) {
      setScrapeError(err.message)
    } finally {
      setScrapeLoading(false)
    }
  }

  return (
    <section className="updates-view">
      <TopBar days={days} onDaysChange={setDays} onFetch={handleFetch} loading={initialLoading || scrapeLoading} />
      {scrapeError && docs.length > 0 && <div className="updates-error" role="alert">{scrapeError}</div>}
      <div className="main">
        <DocumentList
          docs={docs} selected={selected} onSelect={setSelected}
          loading={initialLoading || (scrapeLoading && docs.length === 0)}
          error={initialError || scrapeError}
          fetched={!initialLoading}
          days={days}
          loadingMessage={initialLoading ? 'Loading saved documents…' : undefined}
          emptyMessage={resultSource === 'saved'
            ? 'No saved regulatory documents yet.'
            : `No MAS documents found in the last ${days} days.`}
        />
        <DetailPanel doc={selected} />
      </div>
    </section>
  )
}
