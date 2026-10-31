import { useState } from 'react'
import { Check, ClipboardCheck, X } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth, useToast } from '../contexts/AppContexts'
import { Async, Btn, Empty, Field, Modal, PageHeader, Pill, Table, Tabs, statusTone } from '../components/ui'
import { DAY_NAMES, titleCase } from '../utils/format'

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
          {d.displaced_sessions?.length > 0 && <p className="rounded-xl bg-peach/50 p-3 font-semibold text-[#6b3a14]">Moves these classes (admin approval required): {d.displaced_sessions.join(', ')}</p>}
          {d.needs_approval && <p className="text-muted">Needs approval: {d.needs_approval}.</p>}
          <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-1.5 text-sm">{[['Requester', b.requester || r.requester], ['Attendance', r.attendance], ['Duration', `${r.duration_periods} h`], ['Requested window', r.windows.map((w) => `${w.day} P${w.from_period}-P${w.to_period}`).join(' or ')], ['Venue types', r.room_types.map(titleCase).join(', ')],
            ['Needs', r.needs.length ? r.needs.map(titleCase).join(', ') : 'None'], ['Preferred room', r.requested_room || 'None'], ['Mandatory groups', r.mandatory_for_groups.length ? r.mandatory_for_groups.join(', ') : 'None']].map(([k, v]) => <><dt key={k} className="text-xs font-bold uppercase text-muted">{k}</dt><dd className="font-semibold text-navy">{v}</dd></>)}</dl>
          {canDecide && <Field label="Reason (required only if rejecting)" id="rs"><input id="rs" className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>}
        </div>)}
    </Modal>
  )
}

export default function Bookings() {
  const { user } = useAuth()
  const list = useApi(api.bookings, [])
  const [tab, setTab] = useState('all')
  const [sel, setSel] = useState(null)
  const match = (b) => tab === 'all' || (tab === 'pending' ? b.state === 'proposed' : b.state === tab || b.decision.status === tab)
  const title = user.role === 'club_representative' ? 'My Bookings' : 'Booking Requests'
  return (
    <>
      <PageHeader title={title} subtitle="Every decision follows the published priority order and role caps, and carries a reason. Click a row for the full explanation." />
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
      <Detail b={sel} user={user} onClose={() => setSel(null)} onDone={list.reload} />
    </>
  )
}
