import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Moon, RotateCcw, Sun } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth, useTheme, useToast } from '../contexts/AppContexts'
import { Btn, Card, Field, Modal, PageHeader, Pill, Toggle } from '../components/ui'
import { ROLE_LABEL } from '../utils/nav'

export default function Settings() {
  const { user, logout } = useAuth()
  const { dark, toggle } = useTheme()
  const toast = useToast()
  const nav = useNavigate()
  const health = useApi(api.health, [])
  const ai = useApi(api.aiStatus, [])
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pw, setPw] = useState({ cur: '', next: '' })
  const [pwBusy, setPwBusy] = useState(false)
  const changePw = async (e) => { e.preventDefault(); setPwBusy(true); try { await api.changePassword(pw.cur, pw.next); toast('Password changed', 'ok'); setPw({ cur: '', next: '' }) } catch (x) { toast(x.message, 'error') } finally { setPwBusy(false) } }
  const reset = async () => { setBusy(true); try { const r = await api.demoReset(); toast(`Demo data reset. Timetable ${r.status}.`, 'ok'); setConfirm(false) } catch (e) { toast(e.message, 'error') } finally { setBusy(false) } }
  return (
    <>
      <PageHeader title={user.role === 'admin' ? 'Settings' : 'Profile'} subtitle="Your account, appearance and system information." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Account</h2>
          <dl className="grid grid-cols-[130px_1fr] gap-y-2 text-sm">{[['Name', user.name], ['Role', ROLE_LABEL[user.role]], ['Department', user.department || '-'], ['Faculty ID', user.faculty_id || '-'], ['Student group', user.group_id || '-'], ['Organisation', user.org || '-']].map(([k, v]) => <><dt key={k} className="text-xs font-bold uppercase text-muted">{k}</dt><dd className="font-semibold text-navy">{v}</dd></>)}</dl>
          <Btn variant="peach" className="mt-4" onClick={() => { logout(); nav('/') }}><LogOut className="h-4 w-4" />Sign out</Btn></Card>
        <Card as="form" onSubmit={changePw} className="grid gap-3" aria-label="Change password"><h2 className="text-lg font-bold text-navy">Change password</h2>
          <Field label="Current password" id="cp"><input id="cp" type="password" autoComplete="current-password" required className="field" value={pw.cur} onChange={(e) => setPw({ ...pw, cur: e.target.value })} /></Field>
          <Field label="New password" id="np" hint="At least 10 characters, with letters and a number."><input id="np" type="password" autoComplete="new-password" required className="field" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} /></Field>
          <Btn type="submit" variant="primary" loading={pwBusy} className="w-fit">Update password</Btn></Card>
        <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Appearance</h2>
          <Toggle checked={dark} onChange={toggle} label={dark ? 'Dark mode' : 'Light mode'} /><p className="mt-2 flex items-center gap-2 text-xs text-muted">{dark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}Your choice is remembered on this device.</p>
          <h2 className="mb-2 mt-6 text-lg font-extrabold text-navy">System</h2>
          <div className="flex flex-wrap gap-2"><Pill tone={health.data ? 'ok' : 'warn'}>API {health.data ? 'online' : 'checking'}</Pill>{health.data && <Pill tone="neutral">auth: {health.data.auth_mode}</Pill>}{health.data && <Pill tone="neutral">db: {health.data.database}</Pill>}{ai.data && <Pill tone={ai.data.gemini_configured ? 'lav' : 'neutral'}>Gemini {ai.data.gemini_configured ? 'configured' : 'not configured'}</Pill>}</div></Card>
        {user.role === 'admin' && <Card className="lg:col-span-2"><h2 className="mb-1 text-lg font-extrabold text-navy">Demo data</h2>
          <p className="mb-3 text-sm text-muted">Clears user bookings, disruptions and notifications, and reloads the validated starting timetable so judges can start from a clean state.</p>
          <Btn variant="peach" onClick={() => setConfirm(true)}><RotateCcw className="h-4 w-4" />Reset demo data</Btn></Card>}
      </div>
      <Modal open={confirm} onClose={() => setConfirm(false)} title="Reset demo data?" footer={<><Btn onClick={() => setConfirm(false)}>Cancel</Btn><Btn variant="primary" loading={busy} onClick={reset}>Reset now</Btn></>}>
        <p>This removes all user-submitted bookings, applied disruptions and notifications. The audit log is kept. This cannot be undone.</p></Modal>
    </>
  )
}
