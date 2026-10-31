import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { api } from '../services/api'
import { Logo } from '../components/Logo'
import { Btn, Card, Field } from '../components/ui'
import { useAuth, useToast } from '../contexts/AppContexts'

function Shell({ title, subtitle, children, footer }) {
  return (
    <div className="mx-auto grid min-h-screen max-w-md content-center gap-6 p-4">
      <Link to="/" className="justify-self-center" aria-label="OptiCampus home"><Logo size={72} /></Link>
      <Card className="grid gap-4 p-6 sm:p-8">
        <div><h1 className="text-2xl font-bold text-navy">{title}</h1>{subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}</div>
        {children}
      </Card>
      {footer && <p className="text-center text-sm text-muted">{footer}</p>}
    </div>
  )
}
const Msg = ({ kind = 'error', children }) => children ? <p role={kind === 'error' ? 'alert' : 'status'} className={`rounded-xl px-3 py-2 text-sm font-semibold ${kind === 'error' ? 'tone-bad' : 'tone-ok'}`}>{children}</p> : null

function PasswordInput({ id, value, onChange, label = 'Password', autoComplete = 'current-password', hint }) {
  const [show, setShow] = useState(false)
  return (
    <Field label={label} id={id} hint={hint}>
      <div className="relative">
        <input id={id} className="field pr-12" type={show ? 'text' : 'password'} autoComplete={autoComplete} required value={value} onChange={(e) => onChange(e.target.value)} />
        <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show}
          className="absolute right-2 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-lg text-muted hover:text-navy">{show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}</button>
      </div>
    </Field>
  )
}

export function Login() {
  const { user, login, expired } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const loc = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  if (user) return <Navigate to={loc.state?.from || '/app'} replace />
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setErr('Enter a valid email address')
    setBusy(true)
    try { await login(email.trim(), password, remember); nav(loc.state?.from || '/app', { replace: true }) }
    catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }
  return (
    <Shell title="Sign in" subtitle="Use your OptiCampus account." footer={<>New here? <Link className="font-bold text-accent" to="/request-access">Request access</Link></>}>
      <form onSubmit={submit} noValidate className="grid gap-4" aria-label="Sign in">
        {expired && <Msg>Your session expired. Please sign in again.</Msg>}
        <Field label="Email" id="email"><input id="email" className="field" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <div>
          <PasswordInput id="password" value={password} onChange={setPassword} />
          <div className="mt-2 flex items-center justify-between text-sm">
            <label className="flex items-center gap-2 font-semibold text-navy"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />Remember me</label>
            <Link to="/forgot-password" className="font-bold text-accent">Forgot password?</Link>
          </div>
        </div>
        <Msg>{err}</Msg>
        <Btn type="submit" variant="primary" loading={busy}>Sign in</Btn>
      </form>
    </Shell>
  )
}

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [done, setDone] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setErr('Enter a valid email address')
    setBusy(true)
    try { setDone((await api.forgotPassword(email.trim())).message) } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  return (
    <Shell title="Forgot password" subtitle="Enter your account email and we'll send a reset link." footer={<Link className="font-bold text-accent" to="/login">Back to sign in</Link>}>
      {done ? <Msg kind="ok">{done}</Msg> : (
        <form onSubmit={submit} noValidate className="grid gap-4">
          <Field label="Email" id="fe"><input id="fe" className="field" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Msg>{err}</Msg><Btn type="submit" variant="primary" loading={busy}>Send reset link</Btn>
        </form>)}
    </Shell>
  )
}

export function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    if (pw !== pw2) return setErr('The two passwords do not match')
    setBusy(true)
    try { await api.resetPassword(token, pw); setDone(true) } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  return (
    <Shell title="Set a new password" footer={<Link className="font-bold text-accent" to="/login">Back to sign in</Link>}>
      {!token ? <Msg>This link is missing its reset token. Request a new link from the Forgot password page.</Msg> : done ? (
        <><Msg kind="ok">Password updated. You can now sign in.</Msg><Link to="/login" className="btn btn-primary">Sign in</Link></>) : (
        <form onSubmit={submit} noValidate className="grid gap-4">
          <PasswordInput id="np" label="New password" autoComplete="new-password" value={pw} onChange={setPw} hint="At least 10 characters, with letters and a number." />
          <PasswordInput id="np2" label="Confirm new password" autoComplete="new-password" value={pw2} onChange={setPw2} />
          <Msg>{err}</Msg><Btn type="submit" variant="primary" loading={busy}>Update password</Btn>
        </form>)}
    </Shell>
  )
}

const ROLES = [['faculty', 'Faculty'], ['department_coordinator', 'Department Coordinator'], ['club_representative', 'Club Representative']]
export function RequestAccess() {
  const [f, setF] = useState({ name: '', email: '', password: '', role: 'faculty', department: '', faculty_id: '', organisation: '' })
  const [err, setErr] = useState('')
  const [done, setDone] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }))
  const submit = async (e) => {
    e.preventDefault(); setErr('')
    if (f.name.trim().length < 2) return setErr('Enter your full name')
    if (!/^\S+@\S+\.\S+$/.test(f.email.trim())) return setErr('Enter a valid email address')
    setBusy(true)
    try { setDone((await api.requestAccess({ ...f, email: f.email.trim(), department: f.department || null, faculty_id: f.faculty_id || null, organisation: f.organisation || null })).message) }
    catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  return (
    <Shell title="Request access" subtitle="An administrator reviews every request before the account can be used." footer={<>Already approved? <Link className="font-bold text-accent" to="/login">Sign in</Link></>}>
      {done ? <><Msg kind="ok">{done}</Msg><p className="text-sm text-muted">Status: <b className="text-navy">Pending approval</b></p></> : (
        <form onSubmit={submit} noValidate className="grid gap-4" aria-label="Request access">
          <Field label="Full name" id="rn"><input id="rn" className="field" autoComplete="name" required value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
          <Field label="Institutional email" id="re"><input id="re" className="field" type="email" autoComplete="email" required value={f.email} onChange={(e) => set('email', e.target.value)} /></Field>
          <PasswordInput id="rp" label="Password" autoComplete="new-password" value={f.password} onChange={(v) => set('password', v)} hint="At least 10 characters, with letters and a number." />
          <Field label="Role" id="rr" hint="Admin accounts are created by an existing administrator."><select id="rr" className="field" value={f.role} onChange={(e) => set('role', e.target.value)}>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          {f.role !== 'club_representative' && <Field label="Department" id="rd"><input id="rd" className="field" placeholder="e.g. CSE" value={f.department} onChange={(e) => set('department', e.target.value.toUpperCase())} /></Field>}
          {f.role === 'faculty' && <Field label="Faculty ID (if you know it)" id="rf"><input id="rf" className="field" placeholder="e.g. F12" value={f.faculty_id} onChange={(e) => set('faculty_id', e.target.value.toUpperCase())} /></Field>}
          {f.role === 'club_representative' && <Field label="Club or society" id="ro"><input id="ro" className="field" value={f.organisation} onChange={(e) => set('organisation', e.target.value)} /></Field>}
          <Msg>{err}</Msg><Btn type="submit" variant="primary" loading={busy}>Send request</Btn>
        </form>)}
    </Shell>
  )
}
