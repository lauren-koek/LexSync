import { useState } from 'react'
import AnalysisView from './components/AnalysisView.jsx'
import UpdatesView from './components/UpdatesView.jsx'

export default function App() {
  const [view, setView] = useState('updates')

  return (
    <div className="app">
      <header className="app-header">
        <span className="topbar-title">LexSync</span>
        <nav aria-label="Primary navigation">
          <button aria-pressed={view === 'updates'} onClick={() => setView('updates')}>
            Regulatory Updates
          </button>
          <button aria-pressed={view === 'analysis'} onClick={() => setView('analysis')}>
            Resilience Analysis
          </button>
        </nav>
      </header>
      <div hidden={view !== 'updates'} className="view-container">
        <UpdatesView />
      </div>
      <div hidden={view !== 'analysis'} className="view-container">
        <AnalysisView />
      </div>
    </div>
  )
}
