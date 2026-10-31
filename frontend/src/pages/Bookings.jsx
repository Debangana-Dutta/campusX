import { useState } from 'react'
import { ArrowDown, ArrowUp, CalendarPlus, Check, ClipboardCheck, X } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth, useToast } from '../contexts/AppContexts'
import { Async, Btn, Empty, Field, Modal, PageHeader, Pill, Table, Tabs, statusTone } from '../components/ui'
import { DAYS, DAY_NAMES, PERIOD_TIME, titleCase } from '../utils/format'

function Detail({ b, user, onClose, onDone }) {
  const toast = useToast()
  const [busy, setBusy] = useState('')
  const [reason, setReason] = useState('')
  const [confirm, setConfirm] = useState(null)
  if (!b) return null
  const r = b.request, d = b.decision
  const mine = b.requester_id === user.id
  const canDecide = b.source === 'user' && b.state === 'proposed' && !mine && ['admin', 'department_coordinator'].includes(user.role)
  const run = async (key, fn, ok) => { setBusy(key); try { await fn(); toast(ok, 'ok'); onDone(); onClose() } catch (e) { toast(e.message + (e.detail?.errors ? `: ${e.detail.errors.join('; ')}` : ''), 'error') } finally { setBusy(''); setConfirm(null) } }
  return (
    <Modal open onClose={onClose} title={`${b.id} \u00b7 ${r.title}`}
      footer={confirm ? (<><Btn onClick={() => setConfirm(null)}>Go back</Btn><Btn variant="primary" loading={!!busy} onClick={confirm.fn}>{confirm.label}</Btn></>) : (<>
        {canDecide && <Btn variant="peach" onClick={() => setConfirm({ label: 'Confirm rejection', fn: () => reason.trim() ? run('rej', () => api.decideBooking(b.id, { action: 'reject', reason }), 'Booking rejected') : toast('Give a reason to reject', 'error') })}><X className="h-4 w-4" />Reject</Btn>}
        {canDecide && <Btn variant="mint" onClick={() => setConfirm({ label: 'Confirm approval', fn: () => run('ok', () => api.decideBooking(b.id, { action: 'approve' }), 'Booking approved') })}><Check className="h-4 w-4" />Approve</Btn>}
        {mine && b.state === 'proposed' && d.status === 'alternative_offered' && <><Btn onClick={() => run('no', () => api.respondBooking(b.id, false), 'Alternative declined')}>Decline alternative</Btn><Btn variant="mint" onClick={() => run('yes', () => api.respondBooking(b.id, true), 'Alternative accepted')}>Accept alternative</Btn></>}
        {b.source === 'user' && (mine || user.role === 'admin') && !['cancelled', 'rejected'].includes(b.state) && <Btn onClick={() => setConfirm({ label: 'Yes, cancel booking', fn: () => run('c', () => api.cancelBooking(b.id), 'Booking cancelled') })}>Cancel booking</Btn>}
      </>)}>
      {confirm ? <p className="text-base font-bold text-navy">Are you sure? This is recorded in the audit log.</p> : (
        <div className="grid gap-4">
          <div className="flex flex-wrap gap-2"><Pill tone={statusTone(d.status)}>{titleCase(d.status)}</Pill><Pill tone={statusTone(b.state)}>{titleCase(b.state)}</Pill><Pill tone="lav">{titleCase(d.effective_category || r.requested_category)}</Pill></div>
          {r.raw_text && <div><p className="label">Original request</p><p className="clay-inset p-3 italic text-ink">&ldquo;{r.raw_text}&rdquo;</p></div>}
          <div><p className="label">Decision explanation</p><p className="clay-inset p-3 text-ink">{d.reason}</p></div>
          {d.room_id && <p className="font-bold text-navy">{d.status === 'alternative_offered' ? 'Offered' : 'Placed'}: {d.room_id} &middot; {DAY_NAMES[d.day]} P{d.start_period}-P{d.end_period}</p>}
          {d.displaced_sessions?.length > 0 && <p className="rounded-xl tone-warn p-3 font-semibold">Moves these classes (admin approval required): {d.displaced_sessions.join(', ')}</p>}
          {d.needs_approval && <p className="text-muted">Needs approval: {d.needs_approval}.</p>}
          <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-1.5 text-sm">{[['Requester', b.requester || r.requester], ['Attendance', r.attendance], ['Duration', `${r.duration_periods} h`], ['Requested window', r.windows.map((w) => `${w.day} P${w.from_period}-P${w.to_period}`).join(' or ')], ['Venue types', r.room_types.map(titleCase).join(', ')],
            ['Needs', r.needs.length ? r.needs.map(titleCase).join(', ') : 'None'], ['Preferred room', r.requested_room || 'None'], ['Mandatory groups', r.mandatory_for_groups.length ? r.mandatory_for_groups.join(', ') : 'None']].map(([k, v]) => <><dt key={k} className="text-xs font-bold uppercase text-muted">{k}</dt><dd className="font-semibold text-navy">{v}</dd></>)}</dl>
          {canDecide && <Field label="Reason (required only if rejecting)" id="rs"><input id="rs" className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>}
        </div>)}
    </Modal>
  )
}

function PriorityEditor() {
  const toast = useToast()
  const pr = useApi(api.priority, [])
  const [order, setOrder] = useState(null)
  const cur = order || pr.data?.order || []
  const move = (i, d) => { const o = [...cur]; const j = i + d; if (j < 2 || j >= o.length) return; [o[i], o[j]] = [o[j], o[i]]; setOrder(o) }
  const save = async () => { try { await api.setPriority(cur); toast('Priority order saved. Booking decisions were re-run.', 'ok'); setOrder(null); pr.reload() } catch (e) { toast(e.message, 'error') } }
  if (!pr.data) return null
  return (
    <details className="clay-sm mb-4 p-4"><summary className="cursor-pointer font-bold text-navy">Booking priority order</summary>
      <p className="mt-2 text-xs text-muted">Highest first. Exams and regular classes always come first; the event categories can be reordered.</p>
      <ol className="mt-3 grid gap-1.5">{cur.map((c, i) => <li key={c} className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2 text-sm font-semibold text-navy"><span className="w-5 text-muted">{i + 1}</span>{titleCase(c)}
        {i >= 2 && <span className="ml-auto flex gap-1"><button className="btn !min-h-0 !p-1.5" aria-label={`Move ${c} up`} onClick={() => move(i, -1)} disabled={i === 2}><ArrowUp className="h-4 w-4" /></button><button className="btn !min-h-0 !p-1.5" aria-label={`Move ${c} down`} onClick={() => move(i, 1)} disabled={i === cur.length - 1}><ArrowDown className="h-4 w-4" /></button></span>}</li>)}</ol>
      <Btn variant="primary" className="mt-3" disabled={!order} onClick={save}>Save order</Btn>
    </details>
  )
}

function ManualBooking({ open, onClose, onDone, user }) {
  const toast = useToast()
  const ds = useApi(api.datasetSummary, [], { enabled: open })
  const [f, setF] = useState({ title: '', attendance: 30, duration_periods: 1, room_id: '', day: 'MON', start_period: 10, requested_category: 'department_event', mandatory: '' })
  const [errs, setErrs] = useState([])
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }))
  const go = async () => {
    setBusy(true); setErrs([])
    try { await api.manualBooking({ title: f.title, attendance: +f.attendance, duration_periods: +f.duration_periods, room_id: f.room_id, day: f.day, start_period: +f.start_period, requested_category: f.requested_category, mandatory_for_groups: f.mandatory.split(/[ ,]+/).filter(Boolean).map((x) => x.toUpperCase()) }); toast('Scheduled', 'ok'); onDone(); onClose() }
    catch (e) { setErrs(e.detail?.errors || [e.message]) } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Schedule an event manually" footer={<><Btn onClick={onClose}>Cancel</Btn><Btn variant="primary" loading={busy} onClick={go}>Check and schedule</Btn></>}>
      <p className="mb-3 text-xs text-muted">The same checks as automatic decisions apply: room, time, capacity, features, accessibility, classes and mandatory groups.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Event title" id="mt"><input id="mt" className="field" value={f.title} onChange={(e) => set('title', e.target.value)} /></Field>
        <Field label="Room" id="mr"><select id="mr" className="field" value={f.room_id} onChange={(e) => set('room_id', e.target.value)}><option value="">Choose…</option>{(ds.data?.rooms || []).map((r) => <option key={r.id} value={r.id}>{r.id} ({r.capacity})</option>)}</select></Field>
        <Field label="Day" id="md"><select id="md" className="field" value={f.day} onChange={(e) => set('day', e.target.value)}>{DAYS.map((d) => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}</select></Field>
        <Field label="Start" id="ms"><select id="ms" className="field" value={f.start_period} onChange={(e) => set('start_period', e.target.value)}>{Object.entries(PERIOD_TIME).map(([p, t]) => <option key={p} value={p}>P{p} ({t})</option>)}</select></Field>
        <Field label="Hours" id="mh"><input id="mh" type="number" min="1" className="field" value={f.duration_periods} onChange={(e) => set('duration_periods', e.target.value)} /></Field>
        <Field label="Attendance" id="ma"><input id="ma" type="number" min="1" className="field" value={f.attendance} onChange={(e) => set('attendance', e.target.value)} /></Field>
        <Field label="Mandatory groups (optional)" id="mg"><input id="mg" className="field" placeholder="CSE-3" value={f.mandatory} onChange={(e) => set('mandatory', e.target.value)} /></Field>
      </div>
      {errs.length > 0 && <ul role="alert" className="mt-3 list-disc rounded-xl tone-bad p-3 pl-6 text-sm">{errs.map((e, i) => <li key={i}>{e}</li>)}</ul>}
    </Modal>
  )
}

export default function Bookings() {
  const { user } = useAuth()
  const list = useApi(api.bookings, [])
  const [tab, setTab] = useState('all')
  const [sel, setSel] = useState(null)
  const [manual, setManual] = useState(false)
  const match = (b) => tab === 'all' || (tab === 'pending' ? b.state === 'proposed' : b.state === tab || b.decision.status === tab)
  const title = user.role === 'club_representative' ? 'My Bookings' : ['admin', 'department_coordinator'].includes(user.role) ? 'Requests to Review' : 'My Requests'
  return (
    <>
      <PageHeader title={title} subtitle="Each decision shows its reason. Click a row for details." actions={['admin', 'department_coordinator', 'faculty'].includes(user.role) && <Btn onClick={() => setManual(true)}><CalendarPlus className="h-4 w-4" />Schedule manually</Btn>} />
      {user.role === 'admin' && <PriorityEditor />}
      <div className="mb-4"><Tabs value={tab} onChange={setTab} tabs={[{ id: 'all', label: 'All' }, { id: 'pending', label: 'Needs approval' }, { id: 'approved', label: 'Approved' }, { id: 'alternative_offered', label: 'Alternatives' }, { id: 'rejected', label: 'Rejected' }]} /></div>
      <Async state={list} rows={3} emptyIf={(d) => !d.count} empty={<Empty icon={ClipboardCheck} title="No booking requests yet" hint="Submitted requests and their decisions will appear here." />}>{(d) => {
        const rows = d.bookings.filter(match)
        return rows.length === 0 ? <Empty title="Nothing in this filter" /> : (
          <Table head={['ID', 'Event', 'Requester', 'Category', 'Outcome', 'Status', 'Placement']}>{rows.map((b) => (
            <tr key={b.id} tabIndex={0} role="button" onClick={() => setSel(b)} onKeyDown={(e) => e.key === 'Enter' && setSel(b)} className="cursor-pointer transition hover:bg-lavender/20">
              <td className="td font-bold text-navy">{b.id}</td><td className="td max-w-[220px] truncate">{b.request.title}</td><td className="td">{b.requester || b.request.requester}</td>
              <td className="td">{titleCase(b.decision.effective_category || b.request.requested_category)}</td><td className="td"><Pill tone={statusTone(b.decision.status)}>{titleCase(b.decision.status)}</Pill></td>
              <td className="td"><Pill tone={statusTone(b.state)}>{titleCase(b.state)}</Pill></td><td className="td whitespace-nowrap">{b.decision.room_id ? `${b.decision.room_id} ${b.decision.day} P${b.decision.start_period}-${b.decision.end_period}` : '-'}</td></tr>))}</Table>)
      }}</Async>
      <ManualBooking open={manual} onClose={() => setManual(false)} onDone={list.reload} user={user} />
      <Detail b={sel} user={user} onClose={() => setSel(null)} onDone={list.reload} />
    </>
  )
}
