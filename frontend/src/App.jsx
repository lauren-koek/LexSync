import { useState } from 'react'
import { fetchUpdates } from './api.js'
import DetailPanel from './components/DetailPanel.jsx'
import DocumentList from './components/DocumentList.jsx'
import TopBar from './components/TopBar.jsx'

export default function App() {
  const [days, setDays] = useState(7)
  const [docs, setDocs] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [fetched, setFetched] = useState(false)

  async function handleFetch() {
    setLoading(true)
    setError(null)
    setDocs([])
    setSelected(null)
    try {
      const results = await fetchUpdates(days)
      setDocs(results)
      if (results.length > 0) setSelected(results[0])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setFetched(true)
    }
  }

  return (
    <div className="app">
      <TopBar days={days} onDaysChange={setDays} onFetch={handleFetch} loading={loading} />
      <div className="main">
        <DocumentList
          docs={docs}
          selected={selected}
          onSelect={setSelected}
          loading={loading}
          error={error}
          fetched={fetched}
          days={days}
        />
        <DetailPanel doc={selected} />
      </div>
    </div>
  )
}
