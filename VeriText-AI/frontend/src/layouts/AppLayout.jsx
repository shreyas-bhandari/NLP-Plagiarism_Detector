import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  BookOpen,
  ChevronRight,
  FilePlus2,
  History,
  LayoutDashboard,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import Logo from '../components/Logo'
import { useRequest } from '../hooks/useRequest'
import { getHealth } from '../services/api'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/analysis/new', label: 'New analysis', icon: FilePlus2 },
  { to: '/history', label: 'History', icon: History },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
]

function EngineStatus() {
  const { data } = useRequest(() => getHealth(), [])
  const ready = data?.model?.loaded
  // Device name comes straight from GET /api/health (CUDA only when it is real).
  const device = data?.model?.device
  const gpuName = data?.model?.gpu_name
  const batch = data?.model?.batch_size
  const fallback = data?.model?.fallback_reason
  const deviceLabel = device === 'cuda' ? 'GPU' : device === 'mps' ? 'MPS' : 'CPU'

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
      <div className="flex items-center justify-between gap-1.5">
        <div className="flex items-center gap-1.5">
          <span
            className={`h-1.5 w-1.5 rounded-full ${ready ? 'bg-emerald-400' : 'bg-amber-400'}`}
            aria-hidden="true"
          />
          <p className="text-[11px] font-semibold text-white/85">
            {ready ? 'NLP engine ready' : 'Engine starting'}
          </p>
        </div>
        {device && (
          <span
            className={`rounded border px-1 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.06em] ${
              device === 'cuda'
                ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                : 'border-white/15 bg-white/[0.06] text-white/55'
            }`}
            title={
              fallback ||
              (gpuName
                ? `${gpuName}${batch ? ` · batch ${batch}` : ''}`
                : `CPU inference${batch ? ` · batch ${batch}` : ''}`)
            }
          >
            {deviceLabel}
          </span>
        )}
      </div>
      <p className="mt-1 truncate text-[10.5px] leading-snug text-white/45" title={data?.model?.model}>
        {data?.model?.model?.replace('sentence-transformers/', '') || 'all-MiniLM-L6-v2'}
        {data?.model?.dimension ? ` · ${data.model.dimension}-d` : ''}
      </p>
    </div>
  )
}

export default function AppLayout() {
  const location = useLocation()

  return (
    <div className="min-h-screen lg:flex">
      {/* ------------------------------------------------------------ sidebar */}
      <aside className="scroll-thin hidden w-[248px] shrink-0 flex-col overflow-y-auto border-r border-navy-800/40 bg-navy-950 px-3.5 py-4 lg:sticky lg:top-0 lg:flex lg:h-screen">
        <div className="px-1.5">
          <Logo variant="light" to="/dashboard" />
          <p className="mt-1.5 pl-0.5 text-[10.5px] leading-snug text-white/35">
            Semantic similarity for academic documents
          </p>
        </div>

        <nav className="mt-6 space-y-0.5" aria-label="Main navigation">
          <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-white/30">
            Workspace
          </p>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[12.5px] font-medium transition-colors ${
                  isActive
                    ? 'bg-white/[0.09] text-white'
                    : 'text-white/60 hover:bg-white/[0.05] hover:text-white/90'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`h-4 w-4 ${isActive ? 'text-accent-300' : 'text-white/40'}`} aria-hidden="true" />
                  <span className="flex-1">{label}</span>
                  {isActive && <ChevronRight className="h-3 w-3 text-white/40" aria-hidden="true" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-3">
          <EngineStatus />
          <div className="rounded-lg border border-white/10 px-3 py-2.5">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-white/80">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
              Privacy by default
            </p>
            <p className="mt-1 text-[10.5px] leading-snug text-white/45">
              Document text is deleted from the server after analysis. Only scores and short
              snippets are kept.
            </p>
          </div>
          <p className="px-1 text-[10px] text-white/30">VeriText AI · v1.0</p>
        </div>
      </aside>

      {/* --------------------------------------------------------------- main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-navy-100 bg-white/95 px-4 backdrop-blur lg:px-7">
          <div className="flex min-w-0 items-center gap-3">
            <div className="lg:hidden">
              <Logo to="/dashboard" size="sm" />
            </div>
            <div className="hidden min-w-0 items-center gap-1.5 text-[12px] text-navy-400 lg:flex">
              <span className="font-medium text-navy-500">Workspace</span>
              <ChevronRight className="h-3 w-3" aria-hidden="true" />
              <span className="truncate font-medium text-navy-800">
                {NAV.find((item) => location.pathname.startsWith(item.to))?.label ||
                  (location.pathname.startsWith('/analysis/') ? 'Analysis result' : 'Overview')}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <NavLink to="/analysis/new" className="btn btn-primary btn-sm">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              New analysis
            </NavLink>
          </div>
        </header>

        {/* mobile nav */}
        <nav className="flex gap-1 overflow-x-auto border-b border-navy-100 bg-white px-3 py-1.5 lg:hidden">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-md px-2.5 py-1.5 text-[12px] font-medium ${
                  isActive ? 'bg-navy-900 text-white' : 'text-navy-500 hover:bg-navy-50'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 px-4 py-5 lg:px-7 lg:py-6">
          <Outlet />
        </main>

        <footer className="border-t border-navy-100 px-4 py-3 text-[11px] text-navy-400 lg:px-7">
          VeriText AI measures textual and semantic overlap. It does not determine misconduct —
          human review is always required.
        </footer>
      </div>
    </div>
  )
}
