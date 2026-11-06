import { useState } from 'react'

const HERO = '/images/astronaut-earth.webp'

function Arrow({ diagonal = false }) {
  return <span aria-hidden="true" className="as-arrow">{diagonal ? '↗' : '→'}</span>
}
function Brand({ onClick }) {
  return <button className="as-brand" type="button" onClick={onClick} aria-label="AstroSentinel — homepage"><span className="as-mark" aria-hidden="true" /><span>ASTROSENTINEL</span></button>
}
function TopNav({ navigate, light = false }) {
  const scrollTo = (section) => {
    const target = document.getElementById(section)
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    else navigate('home')
  }
  return <header className={`as-header ${light ? 'as-header--solid' : ''}`}>
    <Brand onClick={() => navigate('home')} />
    <nav className="as-nav" aria-label="Main navigation">
      <button type="button" onClick={() => scrollTo('mission-story')}>The mission</button><button type="button" onClick={() => scrollTo('how-it-works')}>Our approach</button><button type="button" onClick={() => navigate('mission')}>Experience</button>
    </nav>
    <div className="as-nav-right"><button type="button" className="as-text-link" onClick={() => navigate('signin')}>Sign in</button><button type="button" className="as-nav-cta" onClick={() => navigate('mission')}>OPEN THE DEMO <Arrow diagonal /></button></div>
  </header>
}
function Footer({ navigate }) {
  return <footer className="as-footer"><div><Brand onClick={() => navigate('home')} /><small>SHIFU HAWKS · NASA SPACE APPS 2026</small></div><p>Research prototype · Synthetic data only · Not a clinical or flight-qualified system.</p><button type="button" onClick={() => navigate('mission')}>Enter demo <Arrow diagonal /></button></footer>
}

function Landing({ navigate }) {
  return <div className="as-site" id="top">
    <section className="as-hero" style={{ '--hero-image': `url(${HERO})` }}>
      <TopNav navigate={navigate} />
      <div className="as-hero-content">
        <div className="as-index"><i /> MISSION 01 / HUMAN PERFORMANCE IN DEEP SPACE</div>
        <h1>The next frontier<br />is <em>human.</em></h1>
        <p>Spaceflight changes the body. Understanding those changes shouldn’t depend on instant contact with Earth.</p>
        <div className="as-actions"><button type="button" className="as-primary" onClick={() => navigate('mission')}>EXPERIENCE THE MISSION <Arrow diagonal /></button><button type="button" className="as-quiet-cta" onClick={() => document.getElementById('mission-story')?.scrollIntoView({ behavior: 'smooth' })}>EXPLORE OUR APPROACH <Arrow /></button></div>
      </div>
      <div className="as-hero-facts" aria-label="Synthetic mission characteristics"><div><small>MISSION LENGTH</small><strong>030 DAYS</strong></div><div><small>CREW COHORT</small><strong>08 SIMULATED</strong></div><div><small>MONITORING</small><strong>SANS + VENOUS</strong></div><div><small>EARTH LINK</small><strong>0–20 MIN / DEMO</strong></div></div>
    </section>

    <main>
      <section className="as-story as-section" id="mission-story">
        <div><span className="as-eyebrow">01 / THE CHALLENGE</span><h2>Your crew can’t<br />wait for a reply.</h2><p>As distance grows, communication becomes asynchronous. AstroSentinel investigates how a crew could follow personal physiological baselines, track scan quality, and communicate with ground teams through a synthetic 30-day mission.</p></div>
        <aside className="as-story-data" aria-label="Simulated communications example"><div className="as-eyebrow">COMMUNICATION / MISSION-DELAY MODEL</div><div className="as-big-number">13 <span>MINUTES</span></div><p>Illustrative one-way communication delay</p><div className="as-story-columns"><div><small>CREW MISSION DAY</small><strong>30 / 30</strong></div><div><small>GROUND SNAPSHOT</small><strong>DAY 24</strong></div></div><div className="as-story-note">ILLUSTRATIVE SCENARIO · NOT LIVE SPACEFLIGHT TELEMETRY</div></aside>
      </section>
      <section className="as-method as-section" id="how-it-works">
        <span className="as-eyebrow">02 / THE APPROACH</span><h2>Monitor. Measure. Explain.</h2>
        <div className="as-method-row"><span>01</span><h3>Monitor</h3><p>Observe weak signals and personal baselines across the 30-day synthetic mission.</p><small>DAILY RECORDS</small></div>
        <div className="as-method-row"><span>02</span><h3>Measure</h3><p>Show when independent ocular and venous measurements are collected, and whether each is usable.</p><small>SCAN QUALITY</small></div>
        <div className="as-method-row"><span>03</span><h3>Explain</h3><p>Present separate monitoring tiers, evidence, limitations and an auditable decision trail.</p><small>SEPARATE OUTCOMES</small></div>
      </section>
      <section className="as-product as-section"><div className="as-product-copy"><span className="as-eyebrow">03 / THE MISSION WORKSPACE</span><h2>One mission.<br />Every relevant signal.</h2><p>Give crew and ground teams views of the same simulated mission, without confusing unavailable results with zero risk or revealing future measurements.</p><button type="button" className="as-quiet-cta" onClick={() => navigate('dashboard')}>OPEN MISSION CONTROL <Arrow diagonal /></button><div className="as-product-bullets"><span>INDEPENDENT MONITORING</span><span>MEASUREMENT QUALITY</span><span>CAUSAL PLAYBACK</span></div></div><div className="as-product-visual" aria-label="Conceptual mission dashboard preview"><header>ASTROSENTINEL <span>SIMULATION / 030 / 030</span></header><div className="as-product-tiles"><div><small>SANS / OCULAR</small><strong>Unresolved</strong><p>Evidence-dependent monitoring</p></div><div><small>VENOUS / JUGULAR</small><strong>Unresolved</strong><p>Independent monitoring outcome</p></div></div><div className="as-product-chart"><small>OBSERVATION TRACE</small><div className="as-line-viz" aria-hidden="true"><svg viewBox="0 0 550 120" preserveAspectRatio="none"><polyline points="0,80 40,65 80,69 120,34 160,46 200,63 240,22 280,59 320,47 360,72 400,32 440,45 480,17 530,50 550,42" /></svg></div><span>Illustrative only — not experimental data</span></div></div></section>
    </main>
    <Footer navigate={navigate} />
  </div>
}

function Auth({ navigate, signup }) {
  const [notice, setNotice] = useState('')
  return <div className="as-auth"><div className="as-auth-art" style={{ '--hero-image': `url(${HERO})` }}><Brand onClick={() => navigate('home')} /><div className="as-auth-story"><span className="as-eyebrow">DEEP SPACE / HUMAN PERFORMANCE</span><h1>{signup ? <>Build your<br />mission profile.</> : <>Stay close,<br />even from<br />light-minutes away.</>}</h1></div><div className="as-auth-caption">EARTH ↔ MARS / DELAYED GROUND SUPPORT<br /><small>NASA SPACE APPS 2026 / SHIFU HAWKS</small></div></div><main className="as-auth-content"><div className="as-eyebrow">ACCESS SYSTEM / {signup ? 'ENROLLMENT' : 'IDENTIFICATION'}</div><h2>{signup ? 'Create an access profile.' : 'Welcome back.'}</h2><p>{signup ? 'A conceptual mission profile for the demo experience.' : 'Continue to the synthetic mission workspace, or explore without an account.'}</p><form onSubmit={e => { e.preventDefault(); setNotice('Account authentication is not implemented in the research prototype. You can explore the demo without signing in.') }}>
      {signup && <label>FULL NAME<input type="text" autoComplete="name" placeholder="Your name" required /></label>}
      <label>EMAIL ADDRESS<input type="email" autoComplete="email" placeholder="name@example.com" required /></label>
      <label>PASSWORD<input type="password" autoComplete={signup ? 'new-password' : 'current-password'} placeholder={signup ? 'Create a password' : 'Enter your password'} required /></label>
      {!signup && <p className="as-auth-note">Research demo access does not require credentials.</p>}
      <button className="as-primary" type="submit">{signup ? 'CREATE ACCESS PROFILE' : 'SIGN IN'} <Arrow diagonal /></button>
      {notice && <p role="status" className="as-auth-alert">{notice}</p>}
    </form><div className="as-auth-alternate"><button type="button" onClick={() => { setNotice(''); navigate(signup ? 'signin' : 'signup') }}>{signup ? 'Already have an account? Sign in' : 'New to AstroSentinel? Create an account'}</button><div className="as-divider" /><button className="as-link-demo" type="button" onClick={() => navigate('mission')}>EXPLORE DEMO WITHOUT SIGNING IN <Arrow diagonal /></button></div><p className="as-micro">DESIGN CONCEPT · AUTHENTICATION NOT ENABLED</p></main></div>
}

function MissionEntry({ navigate }) {
  const card = (kicker, title, details, action, cls) => <button type="button" className={`as-route-card ${cls}`} onClick={() => navigate('dashboard')}><small>{kicker}</small><h3>{title}</h3><p>{details}</p><strong>{action} <Arrow diagonal /></strong></button>
  return <div className="as-site as-portal" style={{ '--hero-image': `url(${HERO})` }}><TopNav navigate={navigate} light /><main className="as-portal-main"><span className="as-eyebrow">MISSION DECK / SELECT A VIEW</span><h1>Choose where you stand.</h1><p>One synthetic mission. Three perspectives. Every observation remains traceable.</p><div className="as-portal-grid">{card('01 / ONBOARD MONITORING', 'Crew onboard.', 'Follow separate ocular and venous monitoring decisions, measurement quality and evidence limitations.', 'ENTER CREW DECK', 'as-route-card--primary')}<div>{card('02 / EARTH LINK', 'Ground, Earth', 'Review messages, simulated delay and ground acknowledgements.', 'OPEN GROUND VIEW', 'as-route-card--link')}{card('03 / MISSION TIME', '30-day playback', 'Explore time-ordered evidence without exposing future observations.', 'EXPLORE TIMELINE', 'as-route-card--time')}</div></div><p className="as-portal-disclosure">SYNTHETIC RESEARCH DEMONSTRATION · NOT FOR CLINICAL DIAGNOSIS, TREATMENT OR FLIGHT DEPLOYMENT.</p></main></div>
}

export default function Experience({ route, navigate }) {
  if (route === 'signin') return <Auth navigate={navigate} signup={false} />
  if (route === 'signup') return <Auth navigate={navigate} signup />
  if (route === 'mission') return <MissionEntry navigate={navigate} />
  return <Landing navigate={navigate} />
}
