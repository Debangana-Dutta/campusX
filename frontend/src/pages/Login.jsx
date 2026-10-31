import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { GraduationCap, KeyRound, Landmark, PartyPopper, Presentation, Users } from 'lucide-react'
import { Logo } from '../components/Logo'
import { Btn, Card, Field, Pill } from '../components/ui'
import { useAuth, useToast } from '../contexts/AppContexts'

// Demo accounts (LOCAL DEVELOPMENT AUTH). Same password for all; also listed in README.md.
const DEMOS = [
  { u: 'admin', label: 'Admin', sub: "Dean's office", icon: Landmark, tone: 'bg-lavender/70' },
  { u: 'faculty', label: 'Faculty', sub: 'F01 timetable', icon: Presentation, tone: 'bg-mint/70' },
  { u: 'coordinator', label: 'Coordinator', sub: 'CSE department', icon: Users, tone: 'bg-peach/70' },
  { u: 'club', label: 'Club rep', sub: 'Dramatics Society', icon: PartyPopper, tone: 'bg-peri/70' },
  { u: 'student', label: 'Student', sub: 'CSE-2, read-only', icon: GraduationCap, tone: 'bg-sky/70' },
]

export default function Login() {
  const { user, login, expired } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const loc = useLocation()
  const [username, setU] = useState('')
  const [password, setP] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  if (user) return <Navigate to={loc.state?.from || '/app'} replace />

  const submit = async (e, u = username, p = password) => {
    e?.preventDefault(); setBusy(true); setErr('')
    try { await login(u.trim(), p); nav(loc.state?.from || '/app', { replace: true }) }
    catch (ex) { setErr(ex.message); toast(ex.message, 'error') } finally { setBusy(false) }
  }
  return (
    <div className="mx-auto grid min-h-screen max-w-5xl items-center gap-8 p-4 md:grid-cols-2">
      <div className="space-y-6">
        <Link to="/"><Logo size={48} /></Link>
        <h1 className="text-3xl font-extrabold text-navy sm:text-4xl">Welcome back</h1>
        <p className="text-muted">Sign in to manage timetables, venues, exams and schedule changes.</p>
        <Card>
          <Pill tone="warn" className="mb-3">Demo mode &middot; local development authentication</Pill>
          <p className="mb-3 text-sm text-muted">These are fixed demo accounts for judging, not production identities. Pick one (password <code className="rounded bg-surface px-1.5 py-0.5 font-bold text-navy">campusx-demo</code>):</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {DEMOS.map((d) => (
              <button key={d.u} disabled={busy} onClick={() => submit(null, d.u, 'campusx-demo')} className="clay-sm clay-press flex flex-col items-start gap-1 p-3 text-left">
                <span className={`grid h-9 w-9 place-items-center rounded-xl ${d.tone} text-navy`}><d.icon className="h-5 w-5" /></span>
                <span className="text-sm font-extrabold text-navy">{d.label}</span><span className="text-xs text-muted">{d.sub}</span>
              </button>
            ))}
          </div>
        </Card>
      </div>
      <Card as="form" onSubmit={submit} className="space-y-4 p-6 sm:p-8" aria-label="Sign in">
        <h2 className="flex items-center gap-2 text-xl font-extrabold text-navy"><KeyRound className="h-5 w-5 text-accent" />Sign in</h2>
        {expired && <p role="alert" className="rounded-xl bg-peach/60 px-3 py-2 text-sm font-semibold text-[#6b3a14]">Your session expired. Please sign in again.</p>}
        <Field label="Username" id="u"><input id="u" className="field" autoComplete="username" required value={username} onChange={(e) => setU(e.target.value)} placeholder="e.g. admin" /></Field>
        <Field label="Password" id="p"><input id="p" className="field" type="password" autoComplete="current-password" required value={password} onChange={(e) => setP(e.target.value)} /></Field>
        {err && <p role="alert" className="text-sm font-semibold text-bad">{err}</p>}
        <Btn type="submit" variant="primary" loading={busy} className="w-full">Sign in</Btn>
      </Card>
    </div>
  )
}
