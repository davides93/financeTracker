import { RevolutValuation } from './RevolutValuation'
import { RevolutInvestments } from './RevolutInvestments'
import { useState } from 'react'
import './App.css'
import { Portfolio } from './Portfolio'
import { PrivateLedger } from './PrivateLedger'
import type { unlockVault } from './ledgerVault'

type IconName = 'home' | 'wallet' | 'pie' | 'chart' | 'sparkle' | 'plus' | 'arrow' | 'close' | 'calendar' | 'users' | 'lock' | 'repeat' | 'check'

const Icon = ({ name, size = 19 }: { name: IconName; size?: number }) => {
  const paths: Record<IconName, React.ReactNode> = {
    home: <><path d="m3 10 9-7 9 7v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9Z" /><path d="M9 21v-6h6v6" /></>,
    wallet: <><rect x="3" y="6" width="18" height="14" rx="2" /><path d="M3 10h18M16 15h2" /><path d="M6 6V4h10v2" /></>,
    pie: <><path d="M20.9 12A9 9 0 1 1 12 3v9h8.9Z" /><path d="M15 3.3A9 9 0 0 1 20.7 9H15V3.3Z" /></>,
    chart: <><path d="M3 3v18h18" /><path d="m7 16 4-5 3 3 6-8" /><path d="M16 6h4v4" /></>,
    sparkle: <><path d="m12 3-1.4 5.6L5 10l5.6 1.4L12 17l1.4-5.6L19 10l-5.6-1.4L12 3Z" /><path d="m19 15-.7 2.3L16 18l2.3.7L19 21l.7-2.3L22 18l-2.3-.7L19 15Z" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>, arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>, close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 15v2" /></>,
    repeat: <><path d="m17 1 4 4-4 4" /><path d="M3 11V9a4 4 0 0 1 4-4h14" /><path d="m7 23-4-4 4-4" /><path d="M21 13v2a4 4 0 0 1-4 4H3" /></>,
    check: <path d="m5 12 4 4L19 6" />,
  }
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

const navItems: [string, IconName][] = [['Panoramica', 'home'], ['Conti', 'wallet'], ['Spese', 'pie'], ['Portafoglio', 'chart'], ['Condivisi', 'users'], ['Previsioni', 'sparkle']]

function App() {
  const [activeNav, setActiveNav] = useState('Portafoglio')
  const [vault, setVault] = useState<Awaited<ReturnType<typeof unlockVault>>>()
  return <main className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => setActiveNav('Panoramica')} aria-label="Vai alla panoramica"><span className="brand-mark" />Orizzonte</button>
      <nav aria-label="Navigazione principale">{navItems.map(([label, icon]) => <button key={label} onClick={() => setActiveNav(label)} className={activeNav === label ? 'nav-item active' : 'nav-item'}><Icon name={icon} />{label}</button>)}</nav>
      <button className="profile" onClick={() => setActiveNav('Profilo')}><Icon name="lock" /><span><strong>Profilo</strong><small>{vault ? 'Archivio aperto' : 'Accesso e privacy'}</small></span></button>
    </aside>
    <section className="workspace">{vault && (activeNav === 'Portafoglio' || activeNav === 'Previsioni')
      ? <><Portfolio key={activeNav} showForecast={activeNav === 'Previsioni'} report={vault.ledger.portfolio} save={async report => {
          const ledger = { ...vault.ledger, portfolio: report }
          await vault.save(ledger, vault.ledger)
          setVault(current => current?.save === vault.save ? { ...vault, ledger } : current)
        }} />
        {activeNav === 'Portafoglio' && <RevolutInvestments snapshot={vault.ledger.revolutInvestments} save={async revolutInvestments => {
          const ledger = { ...vault.ledger, revolutInvestments }
          await vault.save(ledger, vault.ledger)
          setVault(current => current?.save === vault.save ? { ...vault, ledger } : current)
        }} />}
        {activeNav === 'Portafoglio' && <RevolutValuation snapshot={vault.ledger.revolutInvestments} report={vault.ledger.portfolio} saved={vault.ledger.revolutValuation} save={async (portfolio, revolutValuation) => {
          const ledger = { ...vault.ledger, portfolio, revolutValuation }
          await vault.save(ledger, vault.ledger)
          setVault(current => current?.save === vault.save ? { ...vault, ledger } : current)
        }} />}
      </>
      : <PrivateLedger key={activeNav} page={activeNav} vault={vault} onUnlock={setVault} onLock={() => setVault(undefined)} />}
    </section>
  </main>
}

export default App
