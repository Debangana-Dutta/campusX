import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, Bell, CalendarClock, CalendarDays, CalendarX2, CheckCircle2, ClipboardCheck, GraduationCap, Moon, ShieldCheck, Sun } from 'lucide-react'
import { Logo } from '../components/Logo'
import { useAuth, useTheme } from '../contexts/AppContexts'

const FEATURES = [
  { icon: CalendarDays, title: 'Intelligent timetable scheduling', text: 'Every lecture, tutorial and lab placed in a day, period and room, with every hard rule respected.' },
  { icon: ClipboardCheck, title: 'Venue booking', text: 'Request a room in plain English or Hinglish. See a clear decision and the reason behind it.' },
  { icon: GraduationCap, title: 'Examination planning', text: 'Midsems scheduled across rooms at half capacity, then published to students when ready.' },
  { icon: ShieldCheck, title: 'Clash detection', text: 'Every schedule is verified by the official validator before it can be approved.' },
  { icon: CalendarX2, title: 'Disruption management', text: 'Leave or a closed room? Review exactly which sessions move before an admin applies anything.' },
  { icon: Bell, title: 'Notifications', text: 'The right people hear about approvals, changes and announcements, and no one else.' },
]
const STEPS = [
  ['Load the data', 'Import the campus dataset. Every record is checked before it is used.'],
  ['Generate and verify', 'The solver builds the timetable and exams; the validator confirms there are no clashes.'],
  ['Book and adjust', 'Rooms are requested and decided by fixed priority rules. Changes are proposed, reviewed and approved.'],
]

function Preview({ reduce }) {
  // Illustrative only: structure of the real timetable view, with no figures or claims.
  const tint = ['cc-0', 'cc-1', 'cc-2', 'cc-3', 'cc-4', 'cc-6']
  const filled = new Set([0, 3, 4, 7, 9, 12, 14, 16, 19])
  const float = (d) => (reduce ? {} : { animate: { y: [0, -6, 0] }, transition: { duration: 6 + d, repeat: Infinity, ease: 'easeInOut' } })
  return (
    <div className="relative mx-auto w-full max-w-xl" aria-label="Illustrative preview of the OptiCampus timetable">
      <div className="glass overflow-hidden rounded-3xl p-4 sm:p-5">
        <div className="mb-3 flex items-center justify-between"><span className="tone-neutral rounded-full px-2.5 py-1 text-[11px] font-semibold">Illustrative preview</span><span className="tone-ok inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold"><CheckCircle2 className="h-3.5 w-3.5" />Verified</span></div>
        <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].map((d) => <div key={d} className="text-center text-[11px] font-semibold text-muted">{d}</div>)}
          {Array.from({ length: 25 }, (_, i) => <div key={i} className={`h-8 rounded-lg sm:h-10 ${filled.has(i) ? `${tint[i % 6]} shadow-[inset_1px_1px_3px_rgba(255,255,255,.5)]` : 'clay-inset'}`} />)}
        </div>
      </div>
      <motion.div {...float(0)} className="clay-sm absolute -left-3 -top-5 hidden items-center gap-2 px-3.5 py-2.5 sm:flex"><span className="tone-ok grid h-8 w-8 place-items-center rounded-xl"><CheckCircle2 className="h-4 w-4" /></span><span className="text-sm font-semibold text-navy">No clashes</span></motion.div>
      <motion.div {...float(1.5)} className="clay-sm absolute -bottom-5 -right-3 hidden items-center gap-2 px-3.5 py-2.5 sm:flex"><span className="tone-lav grid h-8 w-8 place-items-center rounded-xl"><CalendarClock className="h-4 w-4" /></span><span className="text-sm font-semibold text-navy">Room free</span></motion.div>
    </div>
  )
}

export default function Landing() {
  const { dark, toggle } = useTheme()
  const { user } = useAuth()
  const reduce = useReducedMotion()
  return (
    <div className="relative overflow-hidden">
      {/* soft ambient shapes (CSS only) */}
      <div aria-hidden className="pointer-events-none absolute -left-24 top-24 h-72 w-72 rounded-full bg-lavender/40 blur-3xl" />
      <div aria-hidden className="pointer-events-none absolute -right-24 top-64 h-72 w-72 rounded-full bg-sky/40 blur-3xl" />
      <div className="relative mx-auto max-w-6xl px-4 pb-10 sm:px-6">
        <header className="glass sticky top-3 z-30 mt-3 flex items-center justify-between rounded-2xl p-2.5 pl-3">
          <Link to="/" aria-label="OptiCampus home"><Logo size={40} /></Link>
          <nav aria-label="Sections" className="hidden items-center gap-6 text-sm font-semibold text-muted md:flex">
            <a href="#features" className="hover:text-navy">Features</a><a href="#how" className="hover:text-navy">How it works</a>
          </nav>
          <div className="flex items-center gap-2">
            <button className="btn !p-2.5" onClick={toggle} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>{dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</button>
            {user ? <Link to="/app" className="btn btn-primary">Open dashboard</Link> : <><Link to="/login" className="btn hidden sm:inline-flex">Sign In</Link><Link to="/request-access" className="btn btn-primary">Get Started</Link></>}
          </div>
        </header>

        <section className="grid items-center gap-12 py-14 sm:py-20 lg:grid-cols-2">
          <motion.div initial={reduce ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}>
            <h1 className="text-4xl font-bold leading-[1.1] tracking-tight text-navy sm:text-5xl lg:text-6xl">Make Every Campus Hour <span className="text-accent">Count.</span></h1>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-muted">Smarter scheduling, seamless venue management and clash-free campus operations.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={user ? '/app' : '/request-access'} className="btn btn-primary !px-6">Get Started<ArrowRight className="h-4 w-4" /></Link>
              <a href="#features" className="btn !px-6">Explore Platform</a>
            </div>
            {!user && <p className="mt-4 text-sm text-muted">Already have an account? <Link to="/login" className="font-semibold text-accent">Sign In</Link></p>}
          </motion.div>
          <Preview reduce={reduce} />
        </section>

        <section id="features" aria-labelledby="f-h" className="scroll-mt-24 py-12">
          <h2 id="f-h" className="text-3xl font-bold tracking-tight text-navy">Everything the campus schedule needs</h2>
          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <article key={f.title} className="clay lift p-6"><span className="tone-lav mb-4 grid h-11 w-11 place-items-center rounded-2xl"><f.icon className="h-5 w-5" /></span>
                <h3 className="text-lg font-bold text-navy">{f.title}</h3><p className="mt-1.5 text-sm leading-relaxed text-muted">{f.text}</p></article>))}
          </div>
        </section>

        <section id="how" aria-labelledby="h-h" className="scroll-mt-24 py-12">
          <h2 id="h-h" className="text-3xl font-bold tracking-tight text-navy">How it works</h2>
          <ol className="mt-8 grid gap-5 md:grid-cols-3">
            {STEPS.map(([t, d], i) => (<li key={t} className="clay-sm lift p-6"><span className="tone-info grid h-9 w-9 place-items-center rounded-xl font-bold">{i + 1}</span><h3 className="mt-3 text-lg font-bold text-navy">{t}</h3><p className="mt-1 text-sm leading-relaxed text-muted">{d}</p></li>))}
          </ol>
        </section>

        <section className="py-12">
          <div className="clay mx-auto max-w-3xl p-8 text-center sm:p-12">
            <h2 className="text-3xl font-bold tracking-tight text-navy">Ready to give your campus its hours back?</h2>
            <p className="mx-auto mt-2 max-w-md text-muted">Request access, or sign in if you already have an account.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3"><Link to="/request-access" className="btn btn-primary !px-7">Get Started<ArrowRight className="h-4 w-4" /></Link><Link to="/login" className="btn !px-7">Sign In</Link></div>
          </div>
        </section>

        <footer className="mt-10 border-t border-[rgb(var(--peri)/.4)] pt-8 text-center">
          <div className="mb-4 flex justify-center"><Logo size={36} /></div>
          <p className="mx-auto max-w-md text-sm text-muted">Designed to make campus operations smarter, simpler and more connected.</p>
          <p className="mt-3 text-sm text-muted">© 2026 OptiCampus. All rights reserved.</p>
        </footer>
      </div>
    </div>
  )
}
