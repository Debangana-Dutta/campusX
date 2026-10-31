import { Link } from 'react-router-dom'
import { GraduationCap, ShieldCheck } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../contexts/AppContexts'
import { Async, Card, Empty, PageHeader, Pill, statusTone } from '../components/ui'
import { DAY_NAMES, PERIOD_TIME, periodEnd, titleCase } from '../utils/format'

const JS_DAY = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
const today = () => JS_DAY[new Date().getDay()]

function ClassList({ entries, title, empty }) {
  return (
    <Card>
      <h2 className="mb-3 text-lg font-extrabold text-navy">{title}</h2>
      {entries.length === 0 ? <Empty title={empty} /> : (
        <ul className="grid gap-2.5">{entries.map((e) => (
          <li key={e.session_id} className="clay-sm flex items-center gap-3 p-3">
            <span className="grid h-11 w-16 shrink-0 place-items-center rounded-xl bg-lavender/60 text-xs font-extrabold text-navy">{PERIOD_TIME[e.start_period]}</span>
            <div className="min-w-0"><p className="truncate text-sm font-extrabold text-navy">{e.course_id} &middot; {e.course_title}</p>
              <p className="truncate text-xs text-muted">{e.room_id} &middot; until {periodEnd(e.end_period)} &middot; {e.faculty_name}</p></div>
          </li>))}</ul>
      )}
    </Card>
  )
}

function StudentFacultyHome({ user }) {
  const isStudent = user.role === 'student'
  const tt = useApi(() => (isStudent ? api.groupTimetable(user.group_id) : api.timetable()), [])
  const ex = useApi(api.exams, [], { enabled: isStudent })
  return (
    <>
      <PageHeader title={`Hello, ${user.name.split(' ')[0]}`} subtitle={isStudent ? `Read-only view for ${user.group_id}.` : `Your teaching schedule (${user.faculty_id}).`} />
      <Async state={tt} rows={3}>{(d) => {
        const mine = d.sessions.filter((e) => (isStudent ? true : e.faculty_id === user.faculty_id))
        const t = today()
        const todays = mine.filter((e) => e.day === t).sort((a, b) => a.start_period - b.start_period)
        const exams = ex.data?.exams || []
        return (
          <div className="grid gap-5 lg:grid-cols-2">
            {t === 'SAT' || t === 'SUN' ? <Card><h2 className="mb-1 text-lg font-extrabold text-navy">Today</h2><Empty title={`No classes on ${DAY_NAMES[t]}`} hint="The teaching week runs Monday to Friday." /></Card>
              : <ClassList entries={todays} title={`Today (${DAY_NAMES[t]})`} empty="No classes today" />}
            <Card><h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-navy"><ShieldCheck className="h-5 w-5 text-ok" />Timetable</h2>
              <Pill tone={statusTone(d.status)}>{titleCase(d.status || 'unknown')}</Pill><p className="mt-2 text-sm text-muted">{mine.length} session(s) a week.</p>
              <Link to="/app/timetable" className="mt-3 inline-block text-sm font-bold text-accent">Open full timetable</Link></Card>
            {isStudent && <Card><h2 className="mb-3 flex items-center gap-2 text-lg font-extrabold text-navy"><GraduationCap className="h-5 w-5 text-accent" />Upcoming exams</h2>
              {exams.length === 0 ? <Empty title="No exams scheduled for you" /> : <ul className="grid gap-2">{exams.slice(0, 4).map((e) => <li key={e.exam_id} className="clay-sm p-3 text-sm"><b className="text-navy">{e.title}</b><br /><span className="text-muted">{e.day} {e.session} &middot; {e.rooms.join(', ')}</span></li>)}</ul>}
              <Link to="/app/exams" className="mt-3 inline-block text-sm font-bold text-accent">All exams</Link></Card>}
          </div>
        )
      }}</Async>
    </>
  )
}

function Row({ label, count, to, hint }) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-xl bg-surface px-4 py-3">
      <div className="min-w-0"><p className="font-semibold text-navy">{label}</p>{hint && <p className="text-xs text-muted">{hint}</p>}</div>
      <div className="flex items-center gap-3"><span className={`text-xl font-bold ${count ? 'text-accent' : 'text-muted'}`}>{count}</span>
        <Link to={to} className="btn !min-h-0 !px-3 !py-1.5 text-xs">Open</Link></div>
    </li>
  )
}

function StaffHome({ user }) {
  const s = useApi(api.summary, [])
  const mine = useApi(api.bookings, [], { enabled: user.role === 'club_representative' })
  const reviewer = user.role === 'admin' || user.role === 'department_coordinator'
  return (
    <>
      <PageHeader title={`Hello, ${user.name.split(' ')[0]}`} actions={user.role === 'club_representative' ? <Link className="btn btn-primary" to="/app/request-venue">Request a venue</Link> : user.role === 'admin' ? <Link className="btn btn-primary" to="/app/generate">Timetable Generator</Link> : null} />
      <Async state={s} rows={2}>{(d) => (
        <div className="grid gap-6 lg:grid-cols-2">
          {reviewer && (
            <Card><h2 className="mb-3 text-lg font-bold text-navy">Needs your attention</h2>
              <ul className="grid gap-2">
                <Row label="Requests to review" count={d.pending_bookings} to="/app/bookings" hint="Room bookings waiting for a decision" />
                {user.role === 'admin' && <Row label="Account requests" count={d.pending_accounts} to="/app/users" />}
                {user.role === 'admin' && <Row label="Schedule changes to approve" count={d.active_disruptions} to="/app/disruptions" />}
              </ul></Card>)}
          <Card><h2 className="mb-3 text-lg font-bold text-navy">Timetable</h2>
            <div className="flex flex-wrap items-center gap-2"><Pill tone={statusTone(d.timetable_status)}>{titleCase(d.timetable_status)}</Pill>
              <span className="text-sm text-muted">{d.sessions_scheduled} of {d.sessions_total} sessions scheduled</span></div>
            {d.validation && <p className="mt-3 text-sm text-ink">Official validator: <b>{d.validation.accepted ? 'accepted' : 'not accepted'}</b> · {d.validation.hard_violation_count} clashes · soft penalty {d.validation.soft_total}</p>}
            <p className="mt-1 text-sm text-muted">{d.exams_scheduled} of {d.exams_total} exams scheduled</p>
            <Link to="/app/timetable" className="mt-3 inline-block text-sm font-bold text-accent">Open timetable</Link></Card>
          {user.role === 'club_representative' && <Card className="lg:col-span-2"><h2 className="mb-3 text-lg font-bold text-navy">My requests</h2>
            <Async state={mine} rows={1} emptyIf={(x) => !x.count} empty={<Empty title="No requests yet" hint="Use Request a venue to send one." />}>{(m) => <ul className="grid gap-2">{m.bookings.slice(0, 5).map((b) => <li key={b.id} className="flex items-center justify-between gap-3 rounded-xl bg-surface px-4 py-3 text-sm"><span className="truncate font-semibold text-navy">{b.request.title}</span><Pill tone={statusTone(b.state)}>{titleCase(b.state)}</Pill></li>)}</ul>}</Async></Card>}
        </div>)}</Async>
    </>
  )
}

export default function Overview() {
  const { user } = useAuth()
  return user.role === 'student' || user.role === 'faculty' ? <StudentFacultyHome user={user} /> : <StaffHome user={user} />
}
