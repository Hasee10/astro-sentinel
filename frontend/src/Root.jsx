import { useEffect, useState } from 'react'
import App from './App.jsx'
import PresentationView from './presentation/PresentationView.jsx'

// Switches between the presentation view (the default, for the demo) and the
// original debug dashboard, which is unchanged. The choice lives in the address
// bar: ".../#debug" opens the debug view, so a reload keeps it.
function currentMode() {
  return window.location.hash === '#debug' ? 'debug' : 'present'
}

export default function Root() {
  const [mode, setMode] = useState(currentMode)

  useEffect(() => {
    const onHashChange = () => setMode(currentMode())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function open(next) {
    window.location.hash = next === 'debug' ? 'debug' : ''
    setMode(next)
    window.scrollTo(0, 0)
  }

  if (mode === 'debug') {
    return (
      <>
        <button type="button" className="mode-switch" onClick={() => open('present')}>
          Presentation view
        </button>
        <App />
      </>
    )
  }
  return <PresentationView onOpenDebug={() => open('debug')} />
}
