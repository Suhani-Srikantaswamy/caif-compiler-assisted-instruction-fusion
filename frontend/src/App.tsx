import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { useApp } from './state/AppState'
import Overview from './pages/Overview'
import InputPage from './pages/InputPage'
import FusionAnalysis from './pages/FusionAnalysis'
import DependencyPage from './pages/DependencyPage'
import OptimizationPage from './pages/OptimizationPage'
import ResultsPage from './pages/ResultsPage'
import AboutPage from './pages/AboutPage'

const NAV = [
  { to: '/', label: 'Overview', n: 1 },
  { to: '/input', label: 'Instruction Input', n: 2 },
  { to: '/analysis', label: 'Fusion Analysis', n: 3 },
  { to: '/dependencies', label: 'Dependency Graph', n: 4 },
  { to: '/optimization', label: 'Optimization', n: 5 },
  { to: '/results', label: 'Results & Experiments', n: 6 },
  { to: '/about', label: 'About & Technical', n: 7 },
]

export default function App() {
  const { backendOk, result } = useApp()
  const location = useLocation()
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-slate-200 bg-slate-100 md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 md:border-b-0 md:border-r">
        <div className="px-5 py-4">
          <div className="text-lg font-bold tracking-tight text-indigo-700">CAIF</div>
          <div className="text-xs leading-snug text-slate-500">Compiler-Assisted Instruction Fusion</div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}
              className={({ isActive }) => `flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`}>
              <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-100 text-[11px] text-slate-500">{n.n}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden space-y-1 px-5 py-3 text-xs text-slate-500 md:block">
          <div>Backend: {backendOk === null ? 'checking...' : backendOk ? <span className="text-emerald-600">connected</span> : <span className="text-red-600">not reachable</span>}</div>
          <div>Last run: {result ? result.status.replace(/_/g, ' ').toLowerCase() : 'none'}</div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8">
        {backendOk === false && (
          <div className="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
            Cannot reach the backend. Start it with <code className="mono">cd backend &amp;&amp; .venv/bin/uvicorn main:app --port 8000</code>.
          </div>
        )}
        <ErrorBoundary resetKey={location.pathname}>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/input" element={<InputPage />} />
          <Route path="/analysis" element={<FusionAnalysis />} />
          <Route path="/dependencies" element={<DependencyPage />} />
          <Route path="/optimization" element={<OptimizationPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}
