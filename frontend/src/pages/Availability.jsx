import { useState } from 'react'
import { CalendarClock, Send } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth, useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, Field, PageHeader, Pill, Table, statusTone } from '../components/ui'
import { DAYS, DAY_NAMES, PERIOD_TIME, titleCase } from '../utils/format'

export default function Availability() {
  const { user } = useAuth()
  const toast = useToast()
  const hist = useApi(api.disruptions, [])
  const [days, setDays] = useState([])
  const [from, setFrom] = useState(1)
  const [to, setTo] = useState(9)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    if (!days.length) return toast('Pick at least one day', 'error')
    if (to < from) return toast('"To" must not be before "From"', 'error')
    setBusy(true); setRes(null)
    try {
      const r = await api.previewDisruption([{ type: 'faculty_unavailable', faculty_id: user.faculty_id, days, periods: Array.from({ length: to - from + 1 }, (_, i) => from + i), reason: reason || 'Faculty unavailability' }], 60)
      setRes(r); hist.reload(); toast('Sent to the admin office for approval. Nothing changes until it is approved.', 'ok')
    } catch (x) { toast(x.message, 'error') } finally { setBusy(false) }
  }
  return (
    <>
      <PageHeader title="Availability" subtitle="Mark when you are unavailable. The system computes the smallest set of timetable moves and sends it to the admin office. You cannot approve your own request." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card as="form" onSubmit={submit} className="grid gap-4" aria-label="Mark unavailability">
          <fieldset><legend className="label">Days</legend><div className="flex flex-wrap gap-2">{DAYS.map((d) => <button type="button" key={d} aria-pressed={days.includes(d)} onClick={() => setDays((s) => s.includes(d) ? s.filter((x) => x !== d) : [...s, d])} className={`pill ${days.includes(d) ? 'bg-lavender/80 text-navy' : 'bg-surface text-muted'}`}>{DAY_NAMES[d]}</button>)}</div></fieldset>
          <div className="grid grid-cols-2 gap-3">{[['From period', from, setFrom, 'f'], ['To period', to, setTo, 't']].map(([l, v, s, id]) => <Field key={id} label={l} id={id}><select id={id} className="field" value={v} onChange={(e) => s(+e.target.value)}>{Object.entries(PERIOD_TIME).filter(([p]) => +p <= 9).map(([p, t]) => <option key={p} value={p}>P{p} ({t})</option>)}</select></Field>)}</div>
          <Field label="Reason" id="r"><input id="r" className="field" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Conference" /></Field>
          <Btn type="submit" variant="primary" loading={busy}><Send className="h-4 w-4" />Request</Btn>
          <p className="text-xs text-muted">Requests for extra or moved sessions are not available in this version; contact your department coordinator.</p>
        </Card>
        <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Proposed effect</h2>
          {!res ? <Empty icon={CalendarClock} title="No request yet" /> : !res.feasible ? <div role="alert"><Pill tone="bad">No valid repair</Pill><p className="mt-2 text-sm text-ink">{res.conflict?.reason}</p></div> : (
            <div className="grid gap-2 text-sm"><Pill tone={statusTone(res.status)}>{titleCase(res.status)} &middot; awaiting admin</Pill><p>{res.summary.moved} session(s) would move. {res.minimality}</p>
              <ul className="grid gap-1.5">{res.moved.map((m) => <li key={m.session_id} className="clay-inset px-3 py-2 text-xs"><b className="text-navy">{m.session_id}</b> {m.from.day} P{m.from.start_period} {m.from.room_id} &rarr; {m.to.day} P{m.to.start_period} {m.to.room_id}</li>)}</ul></div>)}</Card>
        <Card className="lg:col-span-2"><h2 className="mb-3 text-lg font-extrabold text-navy">Change history</h2>
          <Async state={hist} rows={1} emptyIf={(d) => !d.disruptions.length} empty={<Empty title="No requests or changes yet" />}>{(d) => <Table head={['ID', 'Status', 'Requested by', 'Moved', 'When']}>{d.disruptions.map((x) => <tr key={x.id}><td className="td font-bold text-navy">{x.id}</td><td className="td"><Pill tone={statusTone(x.status)}>{titleCase(x.status)}</Pill></td><td className="td">{x.requested_by}</td><td className="td">{x.moved ?? '-'}</td><td className="td">{new Date(x.created_at).toLocaleString()}</td></tr>)}</Table>}</Async></Card>
      </div>
    </>
  )
}
