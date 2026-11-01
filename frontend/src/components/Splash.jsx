import { useEffect, useState } from 'react'
import { LogoMark } from './Logo'
import BrandName from './BrandName'

/** Opening screen: logo + name on translucent glass. After `hold` ms it pulls down and away (`exit` ms), then unmounts,
 *  revealing the login page that was already rendered underneath. */
export default function Splash({ hold = 1000, exit = 700 }) {
  const [phase, setPhase] = useState('show')          // show -> leaving -> gone
  useEffect(() => {
    const a = setTimeout(() => setPhase('leaving'), hold)
    const b = setTimeout(() => setPhase('gone'), hold + exit)
    return () => { clearTimeout(a); clearTimeout(b) }
  }, [hold, exit])
  useEffect(() => {
    if (phase === 'gone') return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [phase])
  if (phase === 'gone') return null
  return (
    <div data-testid="splash" data-phase={phase} aria-hidden="true" className={`splash ${phase === 'leaving' ? 'splash-leave' : ''}`} style={{ '--splash-exit': `${exit}ms` }}>
      <span className="splash-orb bg-lavender/60" style={{ width: 320, height: 320, left: '8%', top: '12%' }} />
      <span className="splash-orb bg-sky/60" style={{ width: 360, height: 360, right: '6%', bottom: '8%' }} />
      <div className="splash-card">
        <LogoMark size={120} />
        <BrandName className="text-5xl sm:text-6xl" />
      </div>
    </div>
  )
}
