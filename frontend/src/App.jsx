import { useState } from 'react'
import { Menu, X } from 'lucide-react'
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
  const [navOpen, setNavOpen] = useState(false)
  const documents = useDocuments()

  return (
    <div className="app-shell">
      <Sidebar view={view} open={navOpen} onNavigate={next => { setView(next); setNavOpen(false) }} />
      {navOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="utility-bar">
          <button className="mobile-menu" aria-label={navOpen ? 'Close navigation' : 'Open navigation'} onClick={() => setNavOpen(value => !value)}>
            {navOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
          <span className="utility-bar__title">{TITLES[view]}</span>
          <span className="utility-bar__context">MAS · Singapore</span>
        </header>
        <main className="app-content">
          {view === 'dashboard' && <UpdatesView documents={documents} />}
          {view === 'changes' && <RegulatoryChangesView documents={documents} />}
          {view === 'map' && <ImpactMapView />}
          {view === 'analysis' && <AnalysisView />}
        </main>
      </div>
    </div>
  )
}
