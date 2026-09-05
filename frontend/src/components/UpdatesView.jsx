import { useState } from 'react'
import DetailPanel from './DetailPanel.jsx'
import DocumentList from './DocumentList.jsx'
import SummaryStrip from './SummaryStrip.jsx'
import TopBar from './TopBar.jsx'
import PageIntro from './ui/PageIntro.jsx'
import { impactLevel } from '../lib/impact.js'

// Dashboard body. Consumes the shared document dataset via the `documents`
// hook object owned by App, and manages its own local selection.
export default function UpdatesView({ documents }) {
  const {
    days,
    setDays,
    docs,
    initialLoading,
    initialError,
    scrapeLoading,
    scrapeError,
    resultSource,
    runFetch,
  } = documents

  const [selectedUrl, setSelectedUrl] = useState(null)
  const selected =
    docs.find(d => d.source_url === selectedUrl) || docs[0] || null
  const highImpact = docs.filter(doc => impactLevel(doc) === 'high').length
  const attention = highImpact === 0
    ? 'No high-impact updates currently need attention.'
    : `${highImpact} high-impact ${highImpact === 1 ? 'update needs' : 'updates need'} attention.`

  const handleFetch = () => runFetch().catch(() => {})
  const handleRefresh = () => runFetch({ refresh: true }).catch(() => {})

  return (
    <div className="dashboard-view">
      <PageIntro
        eyebrow="MAS regulatory workspace"
        title="Regulatory change, made legible."
        description="See what changed, understand the exposure, and move from source material to action without losing the audit trail."
        status={attention}
      />
      <SummaryStrip docs={docs} days={days} />
      <TopBar
        days={days}
        onDaysChange={setDays}
        onFetch={handleFetch}
        onRefresh={handleRefresh}
        loading={initialLoading || scrapeLoading}
      />
      {scrapeError && docs.length > 0 && (
        <div className="decision-red rounded-lg px-4 py-2 text-sm" role="alert">
          {scrapeError}
        </div>
      )}
      <div className="document-workspace">
        <DocumentList
          docs={docs}
          selected={selected}
          onSelect={d => setSelectedUrl(d.source_url)}
          loading={initialLoading || (scrapeLoading && docs.length === 0)}
          error={initialError || scrapeError}
          fetched={!initialLoading}
          days={days}
          loadingMessage={initialLoading ? 'Loading saved documents…' : undefined}
          emptyMessage={
            resultSource === 'saved'
              ? 'No saved regulatory documents yet.'
              : `No MAS documents found in the last ${days} days.`
          }
        />
        <DetailPanel doc={selected} />
      </div>
    </div>
  )
}
