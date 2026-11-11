import { useEffect, useState } from 'react'
import App from './App.jsx'
import PresentationView from './presentation/PresentationView.jsx'
import Experience from './experience/Experience.jsx'
import './experience/experience.css'

// Hash routing keeps the Vite static build deployable without server rewrites.
// All original monitoring behaviour remains in PresentationView. #debug remains
// the unmodified functional dashboard for integration diagnostics.
// signin/signup archived (not deleted): Experience.jsx still has the Auth
// component for later, it's just not reachable - any old #signin/#signup
// link now falls back to home via routeFromHash's ROUTES.has() check.
const ROUTES = new Set(['home', 'mission', 'dashboard', 'debug'])
function routeFromHash() {
  const route = window.location.hash.slice(1).split('?')[0].replace(/^\//, '') || 'home'
  return ROUTES.has(route) ? route : 'home'
}

export default function Root() {
  const [route, setRoute] = useState(routeFromHash)
  useEffect(() => {
    const update = () => { setRoute(routeFromHash()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  const navigate = (to) => { window.location.hash = to === 'home' ? '' : to }

  if (route === 'debug') return (
    <>
      <button type="button" className="mode-switch" onClick={() => navigate('dashboard')}>
        Return to mission dashboard
      </button>
      <App />
    </>
  )

  if (route === 'dashboard') return (
    <div className="as-dashboard-shell">
      <div className="as-dashboard-utility">
        <div className="as-dash-top-brand"><span className="as-mark" aria-hidden="true" /> ASTROSENTINEL <span className="as-util-sub">/ MISSION MONITORING</span></div>
        <div className="as-util-actions">
          <span className="as-online"><span /> SYNTHETIC MISSION</span>
          <button type="button" onClick={() => navigate('mission')}>Mission entry</button>
          <button type="button" onClick={() => navigate('home')}>Website</button>
        </div>
      </div>
      <div className="as-dashboard-context">
        <p className="as-eyebrow">MISSION OPERATIONS / CREW HEALTH RESEARCH</p>
        <div><h1>Mission health overview</h1><p>Independent ocular and venous monitoring across a 30-day synthetic Mars-transit mission.</p></div>
      </div>
      <PresentationView onOpenDebug={() => navigate('debug')} />
    </div>
  )

  return <Experience route={route} navigate={navigate} />
}
