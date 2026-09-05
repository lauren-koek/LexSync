import { LayoutDashboard, ListTree, Network, ShieldCheck } from 'lucide-react'
import logo from '../assets/lexsync-logo.jpg'
import { cn } from '../lib/utils.js'

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'changes', label: 'Regulatory Changes', icon: ListTree },
  { id: 'map', label: 'Impact Map', icon: Network },
  { id: 'analysis', label: 'Resilience Analysis', icon: ShieldCheck },
]

export default function Sidebar({ view, onNavigate, open = false }) {
  return (
    <aside className={`sidebar ${open ? 'sidebar--open' : ''}`}>
      <div className="flex items-center gap-2.5 px-5 py-5">
        <img
          src={logo}
          alt="LexSync"
          className="h-8 w-8 rounded-md object-cover"
        />
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">LexSync</div>
          <div className="text-[11px] text-muted">
            Regulatory workspace
          </div>
        </div>
      </div>

      <nav className="flex flex-col gap-0.5 px-3 py-2" aria-label="Primary">
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = view === id
          return (
            <button
              key={id}
              aria-current={active ? 'page' : undefined}
              onClick={() => onNavigate(id)}
              className={cn(
                'sidebar__nav-item',
                active
                  ? 'sidebar__nav-item--active'
                  : '',
              )}
            >
              <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
              {label}
            </button>
          )
        })}
      </nav>

      <div className="mt-auto border-t border-border px-5 py-4">
        <p className="eyebrow mb-1">Data source</p>
        <p className="text-[12px] leading-snug text-muted">
          MAS regulatory publications. Impact mapping unlocks once internal
          documents are ingested.
        </p>
      </div>
    </aside>
  )
}
