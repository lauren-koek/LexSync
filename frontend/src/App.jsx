import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import UpdatesView from './components/UpdatesView.jsx'
import RegulatoryChangesView from './components/RegulatoryChangesView.jsx'
import ImpactMapView from './components/ImpactMapView.jsx'
import AnalysisView from './components/AnalysisView.jsx'
import useDocuments from './hooks/useDocuments.js'

const TITLES = {
  dashboard: 'Dashboard',
  changes: 'Regulatory Changes',
  map: 'Impact Map',
  analysis: 'Resilience Analysis',
}

export default function App() {
  const [view, setView] = useState('dashboard')
  const documents = useDocuments()

  return (
    <div className="flex h-screen bg-canvas">
      <Sidebar view={view} onNavigate={setView} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center border-b border-border px-6">
          <h1 className="text-sm font-semibold tracking-tight">{TITLES[view]}</h1>
        </header>
        <main className="min-h-0 flex-1 overflow-auto p-6">
          {view === 'dashboard' && <UpdatesView documents={documents} />}
          {view === 'changes' && <RegulatoryChangesView documents={documents} />}
          {view === 'map' && <ImpactMapView />}
          {view === 'analysis' && <AnalysisView />}
        </main>
      </div>
    </div>
  )
}
