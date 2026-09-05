import { Network } from 'lucide-react'
import PageIntro from './ui/PageIntro.jsx'
import WorkspacePanel from './ui/WorkspacePanel.jsx'

export default function ImpactMapView() {
  return (
    <div className="view-stack">
      <PageIntro eyebrow="Relationship view" title="Trace change through every obligation." description="Follow the path from a regulatory source to the policy it affects and the action your team must take." status="Waiting for internal documents" />
      <WorkspacePanel className="impact-empty">
        <div className="max-w-2xl text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-decision-green-bg text-accent-deep">
            <Network size={26} />
          </div>
          <h2 className="text-xl font-medium">Your impact chain will appear here</h2>
          <div className="impact-chain" aria-label="Future impact relationship">
            <span>Regulation</span><b aria-hidden="true">→</b><span>Internal policy</span><b aria-hidden="true">→</b><span>Required action</span>
          </div>
          <p className="text-sm leading-relaxed text-muted">
            This view unlocks once internal documents are ingested. LexSync will connect regulations to affected policies and explain each required action with its source.
          </p>
        </div>
      </WorkspacePanel>
    </div>
  )
}
