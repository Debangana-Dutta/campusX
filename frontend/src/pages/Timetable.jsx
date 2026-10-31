import { useMemo, useState } from 'react'
import { CalendarDays, Download, FileJson, Printer, Search } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth, useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, Field, Modal, PageHeader, Pill, Tabs, statusTone } from '../components/ui'
import { Agenda, RoomMatrix, TimetableGrid } from '../features/timetable/TimetableGrid'
import { courseColor } from '../utils/format'
import { DAYS, DAY_NAMES, download, span, titleCase, toCsv } from '../utils/format'

const VERIFIED = 'Generated using scheduling constraints and verified by the official validator.'
const STATUS_TEXT = {
  approved: `${VERIFIED} Approved by the admin office.`,
  validated: `${VERIFIED} Waiting for admin approval.`,
  draft: 'Draft: not validated yet. Do not rely on it.',
  invalid: 'Invalid: the validator found clashes. Do not use this schedule.',
}

function Why({ id }) {
  const [state, set] = useState(null)
  const go = async () => { set({ loading: true }); try { set({ data: await api.explain(id) }) } catch (e) { set({ error: e.message }) } }
  return (
    <div className="mt-2">
      {!state && <Btn onClick={go}>Why here?</Btn>}
      {state?.loading && <p className="text-sm text-muted" role="status">Checking the schedule…</p>}
      {state?.error && <p className="text-sm text-danger" role="alert">{state.error}</p>}
      {state?.data && <ul className="clay-inset grid gap-1.5 p-3 text-sm text-ink">{state.data.facts.map((f, i) => <li key={i}>{f}</li>)}</ul>}
    </div>
  )
}

function Legend({ entries }) {
  const courses = [...new Map(entries.map((e) => [e.course_id, e.course_title])).entries()].sort()
  if (!courses.length) return null
  return (
    <details className="text-sm" open={courses.length <= 8}>
      <summary className="cursor-pointer font-semibold text-navy">Course colours ({courses.length})</summary>
      <ul className="mt-2 flex flex-wrap gap-2">{courses.map(([id, t]) => <li key={id} className="flex items-center gap-1.5 rounded-lg bg-surface px-2 py-1 text-xs text-ink"><span className={`h-3.5 w-3.5 rounded ${courseColor(id)}`} aria-hidden />{id} {t}</li>)}</ul>
    </details>
  )
}

function Detail({ list, onClose }) {
  return (
    <Modal open={!!list} onClose={onClose} title={list?.length > 1 ? 'Elective basket (all run at the same time)' : list?.[0]?.course_title}>
      <div className="grid gap-4">
        {list?.map((e) => (
          <dl key={e.session_id} className="clay-inset grid grid-cols-[110px_1fr] gap-x-3 gap-y-1.5 p-4">
            {[['Course', `${e.course_id} \u00b7 ${e.course_title}`], ['Type', titleCase(e.kind)], ['When', `${DAY_NAMES[e.day]} ${span(e.start_period, e.end_period)} (P${e.start_period}${e.end_period > e.start_period ? `-P${e.end_period}` : ''})`],
              ['Duration', `${e.end_period - e.start_period + 1} hour(s)`], ['Room', e.room_id], ['Faculty', e.faculty_name], ['Groups', e.groups.join(', ')], ['Size', `${e.size} students`], ['Session ID', e.session_id]]
              .map(([k, v]) => <><dt key={k} className="text-xs font-bold uppercase text-muted">{k}</dt><dd className="font-semibold text-navy">{v}</dd></>)}
          </dl>
        ))}
        {list?.length === 1 && <Why id={list[0].session_id} />}
      </div>
    </Modal>
  )
}

export default function Timetable() {
  const { user } = useAuth()
  const toast = useToast()
  const isStudent = user.role === 'student'
  const isFaculty = user.role === 'faculty'
  const tt = useApi(() => (isStudent ? api.groupTimetable(user.group_id) : api.timetable()), [])
  const ds = useApi(api.datasetSummary, [])
  const [view, setView] = useState(isFaculty ? 'faculty' : 'group')
  const [subject, setSubject] = useState('')
  const [day, setDay] = useState('MON')
  const [mode, setMode] = useState(window.innerWidth < 768 ? 'agenda' : 'grid')
  const [search, setSearch] = useState('')
  const [deptOnly, setDeptOnly] = useState(user.role === 'department_coordinator')
  const [sel, setSel] = useState(null)

  const all = tt.data?.sessions || []
  const facDept = useMemo(() => Object.fromEntries((ds.data?.faculty || []).map((f) => [f.id, f.department])), [ds.data])
  const base = useMemo(() => (deptOnly ? all.filter((e) => facDept[e.faculty_id] === user.department) : all), [all, deptOnly, facDept, user.department])
  const options = useMemo(() => {
    if (view === 'group') return (isStudent ? [{ id: user.group_id, label: user.group_id }] : (ds.data?.groups || []).map((g) => ({ id: g.id, label: g.id })))
    if (view === 'faculty') return (ds.data?.faculty || []).filter((f) => !deptOnly || f.department === user.department).map((f) => ({ id: f.id, label: `${f.name} (${f.id})` }))
    if (view === 'room') return (ds.data?.rooms || []).map((r) => ({ id: r.id, label: `${r.id} \u00b7 ${titleCase(r.type)}` }))
    if (view === 'course') return [...new Map(base.map((e) => [e.course_id, e.course_title])).entries()].sort().map(([id, t]) => ({ id, label: `${id} \u00b7 ${t}` }))
    return []
  }, [view, ds.data, base, isStudent, user, deptOnly])
  const subj = isStudent ? user.group_id : isFaculty && view === 'faculty' ? user.faculty_id : (subject || options[0]?.id)
  const filtered = useMemo(() => {
    let l = base
    if (view === 'group') l = l.filter((e) => e.groups.includes(subj))
    if (view === 'faculty') l = l.filter((e) => e.faculty_id === subj)
    if (view === 'room') l = l.filter((e) => e.room_id === subj)
    if (view === 'course') l = l.filter((e) => e.course_id === subj)
    const s = search.trim().toLowerCase()
    return s ? l.filter((e) => [e.course_id, e.course_title, e.faculty_name, e.room_id].join(' ').toLowerCase().includes(s)) : l
  }, [base, view, subj, search])

  const status = tt.data?.status
  const tabs = isStudent ? [] : isFaculty ? [{ id: 'faculty', label: 'My timetable' }, { id: 'room', label: 'By room' }] :
    [{ id: 'group', label: 'Student group' }, { id: 'faculty', label: 'Faculty' }, { id: 'room', label: 'Room' }, { id: 'course', label: 'Course' }, { id: 'day', label: 'Day' }]

  const exportCsv = () => {
    if (!filtered.length) return toast('Nothing to export for this selection', 'error')
    download(`timetable-${view}-${subj || 'all'}.csv`, toCsv(filtered.map((e) => ({ day: e.day, start: e.start_period, end: e.end_period, course: e.course_id, title: e.course_title, kind: e.kind, room: e.room_id, faculty: e.faculty_name, groups: e.groups.join(' ') }))), 'text/csv')
  }
  const exportSchedule = async () => {
    try { download('schedule.json', JSON.stringify(await api.exportSchedule(), null, 2)); toast('schedule.json exported (official validator accepted)', 'ok') }
    catch (e) { toast(e.message, 'error') }
  }
  return (
    <>
      <PageHeader title={isStudent ? 'My Timetable' : isFaculty ? 'My Timetable' : user.role === 'department_coordinator' ? 'Department Timetable' : 'Timetable'}
        subtitle="Click a class for details. Each course keeps the same colour in every view."
        actions={<>
          <Btn onClick={exportCsv}><Download className="h-4 w-4" />CSV</Btn>
          <Btn onClick={() => window.print()}><Printer className="h-4 w-4" />Print</Btn>
          {user.role === 'admin' && <Btn variant="primary" onClick={exportSchedule}><FileJson className="h-4 w-4" />Export schedule.json</Btn>}
        </>} />
      <Async state={tt} rows={4} emptyIf={(d) => !d.sessions?.length} empty={<Empty icon={CalendarDays} title="No timetable yet" hint={user.role === 'admin' ? 'Open Generate Timetable to create one.' : 'The admin office has not published a timetable yet.'} />}>
        {() => (
          <div className="grid gap-4">
            {status && <div className="flex flex-wrap items-center gap-3"><Pill tone={statusTone(status)}>{titleCase(status)}</Pill><p className="text-sm text-muted">{STATUS_TEXT[status]}</p></div>}
            <Card className="grid gap-4">
              <div className="flex flex-wrap items-end gap-3">
                {tabs.length > 0 && <Tabs tabs={tabs} value={view} onChange={(v) => { setView(v); setSubject('') }} />}
                {view === 'day' ? (
                  <Field label="Day" id="day"><select id="day" className="field" value={day} onChange={(e) => setDay(e.target.value)}>{DAYS.map((d) => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}</select></Field>
                ) : !(isStudent || (isFaculty && view === 'faculty')) && (
                  <Field label={titleCase(view)} id="subj"><select id="subj" className="field min-w-[220px]" value={subj || ''} onChange={(e) => setSubject(e.target.value)}>{options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</select></Field>
                )}
                <div className="relative min-w-[180px] flex-1 sm:max-w-xs"><label htmlFor="ts" className="label">Search</label><Search className="pointer-events-none absolute bottom-3.5 left-3.5 h-4 w-4 text-muted" />
                  <input id="ts" className="field !pl-10" placeholder="Course, faculty or room" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
                <Tabs tabs={[{ id: 'grid', label: 'Grid' }, { id: 'agenda', label: 'Agenda' }]} value={mode} onChange={setMode} />
                {user.role === 'department_coordinator' && <label className="flex items-center gap-2 pb-3 text-sm font-bold text-navy"><input type="checkbox" checked={deptOnly} onChange={(e) => setDeptOnly(e.target.checked)} />{user.department} only</label>}
              </div>
              {view === 'day' ? <RoomMatrix entries={base} day={day} rooms={ds.data?.rooms || []} onSelect={setSel} />
                : filtered.length === 0 ? <Empty title="No sessions match" hint="Try another selection or clear the search." />
                : mode === 'grid' ? <TimetableGrid entries={filtered} onSelect={setSel} /> : <Agenda entries={filtered} onSelect={setSel} />}
              {view === 'day' ? <p className="text-xs text-muted">Green cells are free rooms.</p> : <Legend entries={filtered} />}
            </Card>
          </div>
        )}
      </Async>
      <Detail list={sel} onClose={() => setSel(null)} />
    </>
  )
}
