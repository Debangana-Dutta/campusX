import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, BellRing, CalendarX2, CheckCheck, ClipboardCheck, GraduationCap, Megaphone, Send } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth, useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, Field, PageHeader, Pill } from '../components/ui'

const ICON = { booking: ClipboardCheck, alternative: ClipboardCheck, timetable: BellRing, exam: GraduationCap, disruption: CalendarX2, announcement: Megaphone }

export default function Notifications() {
  const { user } = useAuth()
  const toast = useToast()
  const n = useApi(api.notifications, [])
  const [msg, setMsg] = useState('')
  const [aud, setAud] = useState('all')
  const [busy, setBusy] = useState(false)
  const read = async (ids) => { try { await api.markRead(ids); n.reload() } catch (e) { toast(e.message, 'error') } }
  const send = async (e) => {
    e.preventDefault(); setBusy(true)
    try { await api.announce(msg, aud); toast('Announcement sent', 'ok'); setMsg(''); n.reload() } catch (x) { toast(x.message, 'error') } finally { setBusy(false) }
  }
  return (
    <>
      <PageHeader title="Notifications" subtitle="Created by real events: booking decisions, timetable changes, disruptions, exams and announcements."
        actions={<Btn onClick={() => read(undefined)} disabled={!n.data?.unread}><CheckCheck className="h-4 w-4" />Mark all as read</Btn>} />
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Async state={n} rows={3} emptyIf={(d) => !d.items.length} empty={<Empty icon={Bell} title="You're all caught up" hint="New booking decisions, schedule changes and announcements will appear here." />}>{(d) => (
            <ul className="grid gap-3">{d.items.map((i) => { const I = ICON[i.kind] || Bell; return (
              <li key={i.id} className={`clay-sm flex items-start gap-3 p-4 ${i.read ? 'opacity-75' : ''}`}>
                <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-2xl ${i.read ? 'bg-surface' : 'bg-lavender/70'} text-navy`}><I className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-navy">{i.message}</p>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">{new Date(i.created_at).toLocaleString()}<Pill tone="neutral">{i.kind}</Pill>{i.link && <Link to={i.link} className="font-bold text-accent" onClick={() => !i.read && read([i.id])}>Open</Link>}</p></div>
                {!i.read && <button className="btn !min-h-0 !px-3 !py-1.5 text-xs" onClick={() => read([i.id])}>Mark read</button>}
              </li>) })}</ul>)}</Async>
        </div>
        {user.role === 'admin' && (
          <Card as="form" onSubmit={send} className="grid h-fit gap-3" aria-label="Send announcement">
            <h2 className="text-lg font-extrabold text-navy">Send an announcement</h2>
            <Field label="Audience" id="aud"><select id="aud" className="field" value={aud} onChange={(e) => setAud(e.target.value)}>{[['all', 'Everyone'], ['student', 'Students'], ['faculty', 'Faculty'], ['department_coordinator', 'Coordinators'], ['club_representative', 'Club representatives']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
            <Field label="Message" id="m"><textarea id="m" rows={4} className="field" value={msg} onChange={(e) => setMsg(e.target.value)} maxLength={400} required minLength={3} /></Field>
            <Btn type="submit" variant="primary" loading={busy}><Send className="h-4 w-4" />Send</Btn>
          </Card>)}
      </div>
    </>
  )
}
