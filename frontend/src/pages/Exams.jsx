import { useMemo, useState } from 'react'
import { CheckCircle2, Download, GraduationCap, RefreshCw } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth, useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, PageHeader, Pill, Stat, Table, Tabs } from '../components/ui'
import { download, toCsv } from '../utils/format'

export default function Exams() {
  const { user } = useAuth()
  const toast = useToast()
  const ex = useApi(api.exams, [])
  const ds = useApi(api.datasetSummary, [], { enabled: user.role !== 'student' })
  const [tab, setTab] = useState('calendar')
  const [busy, setBusy] = useState(false)
  const cap = useMemo(() => Object.fromEntries((ds.data?.rooms || []).map((r) => [r.id, r.capacity])), [ds.data])
  const regen = async () => { setBusy(true); try { await api.generateExams(); toast('Exam timetable regenerated', 'ok'); ex.reload() } catch (e) { toast(e.message, 'error') } finally { setBusy(false) } }
  const exportCsv = () => { const l = ex.data?.exams || []; if (l.length) download('exams.csv', toCsv(l.map((e) => ({ exam: e.exam_id, title: e.title, day: e.day, session: e.session, rooms: e.rooms.join(' '), size: e.size, seats_half_capacity: e.seats_at_half_capacity }))), 'text/csv') }
  return (
    <>
      <PageHeader title="Examinations" subtitle="Midsem exams from the dataset. Exam seats are half of each room's capacity; one exam may use several rooms."
        actions={<><Btn onClick={exportCsv}><Download className="h-4 w-4" />CSV</Btn>{user.role === 'admin' && <Btn variant="primary" loading={busy} onClick={regen}><RefreshCw className="h-4 w-4" />Regenerate</Btn>}</>} />
      <Async state={ex} rows={3} emptyIf={(d) => !d.exams.length} empty={<Empty icon={GraduationCap} title="No exams to show" hint={user.role === 'student' ? 'No exams are scheduled for your group yet.' : 'Generate the exam timetable from Generate Timetable.'} />}>{(d) => {
        const sl = d.calendar.sessions, days = d.calendar.days
        const perGroupDay = {}; for (const e of d.exams) for (const g of e.groups) { const k = `${g}|${e.day}`; (perGroupDay[k] ||= []).push(e.exam_id) }
        const crowded = Object.entries(perGroupDay).filter(([, v]) => v.length > 1)
        const groups = [...new Set(d.exams.flatMap((e) => e.groups))].sort()
        return (
          <div className="grid gap-5">
            <div className="grid gap-4 sm:grid-cols-3"><Stat icon={GraduationCap} tone="peri" label="Exams" value={d.exams.length} /><Stat icon={CheckCircle2} tone="mint" label="Seats cover every exam" value={d.exams.every((e) => e.seats_at_half_capacity >= e.size) ? 'Yes' : 'No'} hint="at half capacity" />
              <Stat label="Multi-room exams" value={d.exams.filter((e) => e.rooms.length > 1).length} /></div>
            <Tabs value={tab} onChange={setTab} tabs={[{ id: 'calendar', label: 'Calendar' }, { id: 'table', label: 'Timetable' }, { id: 'rooms', label: 'Room allocation' }, { id: 'conflicts', label: 'Group conflicts' }]} />
            {tab === 'calendar' && <div className="clay-inset overflow-x-auto p-3"><div className="grid min-w-[720px] gap-2" style={{ gridTemplateColumns: `90px repeat(${days.length}, 1fr)` }}>
              <div />{days.map((x) => <div key={x} className="text-center text-xs font-extrabold uppercase text-navy">{x}</div>)}
              {sl.flatMap((s) => [<div key={s.id} className="grid place-items-center text-xs font-bold text-muted">{s.id}<br />{s.start}-{s.end}</div>, ...days.map((x) => (
                <div key={x + s.id} className="grid min-h-[84px] content-start gap-1.5 rounded-2xl border border-[rgb(var(--peri)/.22)] p-1.5">{d.exams.filter((e) => e.day === x && e.session === s.id).map((e) => <div key={e.exam_id} className="rounded-xl bg-lavender/60 px-2 py-1 text-[11px] font-bold leading-tight text-navy" title={e.title}>{e.exam_id.replace('EX-', '')}<br /><span className="font-semibold opacity-80">{e.groups.length > 1 ? `${e.groups.length} groups` : e.groups[0]}</span></div>)}</div>))])}</div></div>}
            {tab === 'table' && <Table head={['Exam', 'Course', 'Day', 'Slot', 'Groups', 'Students']}>{d.exams.map((e) => <tr key={e.exam_id}><td className="td font-bold text-navy">{e.exam_id}</td><td className="td">{e.title}</td><td className="td">{e.day}</td><td className="td">{e.session}</td><td className="td">{e.groups.join(', ')}</td><td className="td">{e.size}</td></tr>)}</Table>}
            {tab === 'rooms' && <Table head={['Exam', 'Rooms', 'Seats (half capacity)', 'Students', 'Check']}>{d.exams.map((e) => <tr key={e.exam_id}><td className="td font-bold text-navy">{e.exam_id}</td>
              <td className="td">{e.rooms.map((r) => <Pill key={r} tone="info" className="mr-1">{r}{cap[r] ? ` ${Math.floor(cap[r] / 2)}` : ''}</Pill>)}</td><td className="td">{e.seats_at_half_capacity}</td><td className="td">{e.size}</td>
              <td className="td"><Pill tone={e.seats_at_half_capacity >= e.size ? 'ok' : 'bad'}>{e.seats_at_half_capacity >= e.size ? 'Fits' : 'Short'}</Pill></td></tr>)}</Table>}
            {tab === 'conflicts' && <Card><p className="mb-3 text-sm text-muted">No group sits two exams in the same slot (hard rule, enforced). Same-day pairs are a soft penalty.</p>
              {crowded.length === 0 ? <p className="flex items-center gap-2 font-bold text-ok"><CheckCircle2 className="h-5 w-5" />No group has two exams on the same day.</p> : <ul className="grid gap-1.5">{crowded.map(([k, v]) => <li key={k} className="clay-inset px-3 py-2 text-sm">{k.replace('|', ' on ')}: {v.join(', ')}</li>)}</ul>}
              <p className="mt-3 text-xs text-muted">{groups.length} group(s) checked.</p></Card>}
          </div>)
      }}</Async>
    </>
  )
}
