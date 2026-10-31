import { useState } from 'react'
import { CheckCircle2, ShieldAlert } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { Async, Btn, Card, Empty, PageHeader, Pill, Stat, Table } from '../components/ui'
import { RULE_TEXT } from '../utils/format'
import { Link } from 'react-router-dom'

const ids = (t) => [...new Set(t.match(/\b[A-Z]{2,4}\d{3}[A-Z0-9-]*\b/g) || [])]

export default function Validation() {
  const st = useApi(api.validate, [])
  const [open, setOpen] = useState(null)
  return (
    <>
      <PageHeader title="Validation" subtitle="Live result from the official validator for the current schedule."
        actions={<Btn onClick={st.reload} loading={st.loading}>Re-run validator</Btn>} />
      <Async state={st} rows={3}>{(d) => (
        <div className="grid gap-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat icon={d.accepted ? CheckCircle2 : ShieldAlert} tone={d.accepted ? 'mint' : 'rose'} label="Verdict" value={d.accepted ? 'Accepted' : 'Not accepted'} hint={`validator exit code ${d.exit_code}`} />
            <Stat label="Hard violations" value={d.hard_violation_count} hint="Must be 0" />
            <Stat label="Soft penalty" value={d.soft_total} hint={Object.entries(d.soft_penalties || {}).map(([k, v]) => `${k}:${v}`).join(' ')} />
            <Stat label="Booking score" value={d.booking ? `${d.booking.booking_score} / ${d.booking.booking_score_max_if_all_approved}` : '-'} hint={d.booking ? `${d.booking.approved} approved, ${d.booking.alternatives} alt, ${d.booking.rejected} rejected` : ''} />
          </div>
          <Card>
            <h2 className="mb-3 text-lg font-extrabold text-navy">Hard violations by rule</h2>
            {d.hard_violation_count === 0 ? <p className="text-sm text-muted">None. Every hard constraint holds for timetable, bookings and exams.</p> : (
              <div className="grid gap-2">{Object.entries(d.hard_by_rule).map(([rule, n]) => <div key={rule} className="clay-sm flex items-center gap-3 p-3 text-sm"><Pill tone="bad">{rule} &times; {n}</Pill><span className="text-ink">{RULE_TEXT[rule] || 'See details below'}</span></div>)}</div>)}
          </Card>
          <Card>
            <h2 className="mb-3 text-lg font-extrabold text-navy">Details</h2>
            {d.hard_violations?.length ? <Table head={['Rule', 'Where', 'Detail', 'Sessions']}>{d.hard_violations.map((v, i) => (
              <tr key={i}><td className="td"><Pill tone="bad">{v.rule}</Pill></td><td className="td">{v.where}</td><td className="td">{v.detail}</td>
                <td className="td">{ids(v.detail).map((s) => <Link key={s} to="/app/timetable" className="mr-1 inline-block"><Pill tone="info">{s}</Pill></Link>)}</td></tr>))}</Table> : <Empty title="No violations to inspect" />}
            {d.warnings?.length > 0 && <div className="mt-4"><h3 className="mb-1 text-sm font-extrabold text-navy">Validator warnings</h3><ul className="list-disc pl-5 text-sm text-muted">{d.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
            {d.priority_inversions?.length > 0 && <div className="mt-4"><h3 className="mb-1 text-sm font-extrabold text-navy">Priority inversions</h3><pre className="clay-inset overflow-auto p-3 text-xs">{JSON.stringify(d.priority_inversions, null, 2)}</pre></div>}
            {d.stability && <p className="mt-4 text-sm text-muted">Moved sessions vs baseline: <b className="text-navy">{d.stability.sessions_moved}</b> ({d.stability.time_changed} time changes, {d.stability.room_only_changed} room-only).</p>}
          </Card>
        </div>)}</Async>
    </>
  )
}
