import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Bot, Building2, CalendarX2, GraduationCap, Moon, ShieldCheck, Sparkles, Sun, Wand2 } from 'lucide-react'
import { Logo } from '../components/Logo'
import { useTheme } from '../contexts/AppContexts'

const features = [
  { icon: Wand2, title: 'Constraint-based timetables', text: 'OR-Tools CP-SAT places every session in a day, period and room. Hard constraints are never traded for a better score.', tone: 'bg-lavender/70' },
  { icon: ShieldCheck, title: 'Checked by the official validator', text: 'Every schedule is run through the organisers\u2019 validator before it can be approved or exported.', tone: 'bg-mint/70' },
  { icon: Building2, title: 'Transparent venue decisions', text: 'Spectra week bookings follow the published priority order, with a reason for every approval, alternative and rejection.', tone: 'bg-peach/70' },
  { icon: CalendarX2, title: 'Minimum-disruption changes', text: 'Faculty leave or a closed room? Preview exactly which sessions move, then approve. Nothing applies automatically.', tone: 'bg-peri/70' },
  { icon: GraduationCap, title: 'Exam scheduling', text: 'Midsems are allocated across rooms at half capacity, without group or room clashes.', tone: 'bg-sky/70' },
  { icon: Bot, title: 'Campus Buddy', text: 'Ask in English or Hinglish. Answers come from your real timetable; AI never decides validity.', tone: 'bg-rose/70' },
]
const steps = [['Load', 'Import the CIT dataset and verify its integrity.'], ['Solve', 'Generate a clash-free timetable, exams and bookings.'], ['Validate', 'The official validator must report zero hard violations.'], ['Adapt', 'Preview changes, review the diff, then approve and apply.']]

function Preview() {
  // Illustrative only: a structural mock of the timetable grid with no real numbers or claims.
  const cols = ['bg-lavender/70', 'bg-mint/70', 'bg-peach/70', 'bg-peri/70', 'bg-sky/70']
  return (
    <div className="clay relative mx-auto w-full max-w-3xl p-4 sm:p-6" aria-label="Illustrative preview of the timetable view">
      <div className="mb-3 flex items-center justify-between"><span className="pill bg-surface text-muted">Illustrative preview</span><span className="pill bg-mint/70 text-[#14513f]">Validated</span></div>
      <div className="grid grid-cols-5 gap-2 sm:gap-3">
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].map((d) => <div key={d} className="text-center text-xs font-bold text-muted">{d}</div>)}
        {Array.from({ length: 20 }, (_, i) => {
          const on = [0, 3, 6, 7, 9, 11, 12, 14, 16, 18].includes(i)
          return <div key={i} className={`h-9 rounded-xl sm:h-12 ${on ? `${cols[i % 5]} shadow-[inset_2px_2px_4px_rgba(255,255,255,.7),inset_-2px_-2px_5px_rgba(0,0,0,.07)]` : 'clay-inset'}`} />
        })}
      </div>
    </div>
  )
}

export default function Landing() {
  const { dark, toggle } = useTheme()
  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
      <header className="clay sticky top-3 z-20 mt-3 flex items-center justify-between p-3">
        <Logo />
        <nav className="hidden items-center gap-6 text-sm font-bold text-muted md:flex" aria-label="Sections">
          <a href="#features" className="hover:text-navy">Features</a><a href="#how" className="hover:text-navy">How it works</a><a href="#buddy" className="hover:text-navy">Campus Buddy</a>
        </nav>
        <div className="flex items-center gap-2">
          <button className="btn !p-2.5" onClick={toggle} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>{dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</button>
          <Link to="/login" className="btn btn-primary">Sign in</Link>
        </div>
      </header>

      <section className="py-14 text-center sm:py-20">
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}>
          <span className="pill bg-lavender/60 text-[#2f2670] dark:text-lavender"><Sparkles className="h-3.5 w-3.5" />Campus scheduling, validated</span>
          <h1 className="mx-auto mt-5 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight text-navy sm:text-6xl">One Campus. <span className="text-accent">Zero Clashes.</span></h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-muted sm:text-lg">Meet the smarter way to manage academic timetables, campus venues, examinations and unexpected schedule changes.</p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a href="#features" className="btn btn-primary !px-6">Explore Campus X<ArrowRight className="h-4 w-4" /></a>
            <Link to="/login" className="btn !px-6">Sign In</Link>
          </div>
        </motion.div>
        <div className="mt-12"><Preview /></div>
      </section>

      <section id="features" className="scroll-mt-24 py-10">
        <h2 className="text-center text-3xl font-extrabold text-navy">What Campus X does</h2>
        <p className="mx-auto mt-2 max-w-xl text-center text-muted">Capabilities of the product as built.</p>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <motion.article key={f.title} whileHover={{ y: -4 }} className="clay p-6">
              <div className={`mb-4 grid h-12 w-12 place-items-center rounded-2xl ${f.tone} text-navy`}><f.icon className="h-6 w-6" /></div>
              <h3 className="text-lg font-extrabold text-navy">{f.title}</h3><p className="mt-1.5 text-sm text-muted">{f.text}</p>
            </motion.article>
          ))}
        </div>
      </section>

      <section id="how" className="scroll-mt-24 py-10">
        <h2 className="text-center text-3xl font-extrabold text-navy">How it works</h2>
        <ol className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(([t, d], i) => (
            <li key={t} className="clay p-6"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-peri/70 font-extrabold text-navy">{i + 1}</span>
              <h3 className="mt-3 text-lg font-extrabold text-navy">{t}</h3><p className="mt-1 text-sm text-muted">{d}</p></li>
          ))}
        </ol>
      </section>

      <section id="buddy" className="scroll-mt-24 py-10">
        <div className="clay grid items-center gap-8 p-6 sm:p-10 md:grid-cols-2">
          <div>
            <span className="pill bg-rose/70 text-[#7a1f3a]"><Bot className="h-3.5 w-3.5" />Campus Buddy</span>
            <h2 className="mt-3 text-3xl font-extrabold text-navy">AI that assists. Code that decides.</h2>
            <p className="mt-3 text-muted">The assistant reads requests and explains your timetable in English or Hinglish. Every booking and schedule is still decided and validated by deterministic code, and the manual forms keep working if the AI is unavailable.</p>
          </div>
          <div className="clay-inset space-y-3 p-5 text-sm">
            <p className="ml-auto w-fit max-w-[85%] rounded-2xl bg-lavender/60 px-4 py-2.5 font-semibold text-navy">Aaj meri next class kaha hai?</p>
            <p className="w-fit max-w-[85%] rounded-2xl bg-surface px-4 py-2.5 text-ink">Answers are built from the signed-in user\u2019s own timetable data.</p>
          </div>
        </div>
      </section>

      <section className="py-10 text-center">
        <div className="clay mx-auto max-w-3xl p-8 sm:p-12">
          <h2 className="text-3xl font-extrabold text-navy">Ready to see it work?</h2>
          <p className="mt-2 text-muted">Sign in with a demo account for each role.</p>
          <Link to="/login" className="btn btn-primary mt-6 !px-8">Sign In<ArrowRight className="h-4 w-4" /></Link>
        </div>
      </section>
      <footer className="flex flex-wrap items-center justify-between gap-3 pt-6 text-sm text-muted"><Logo size={28} /><p>Campus X &middot; One Campus. Zero Clashes. Smarter Decisions.</p></footer>
    </div>
  )
}
