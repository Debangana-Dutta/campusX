import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Bell, Bot, CalendarCheck, CalendarX2, ClipboardCheck, GraduationCap, Send, ShieldCheck, Sparkles, Wand2 } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, PageHeader, Pill, Stat, statusTone } from '../components/ui'
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

function MiniBuddy() {
  const [q, setQ] = useState('')
  const [ans, setAns] = useState(null)
  const [busy, setBusy] = useState(false)
  const ask = async (e) => { e.preventDefault(); if (!q.trim()) return; setBusy(true); try { setAns(await api.ask(q)) } catch (x) { setAns({ answer: x.message }) } finally { setBusy(false) } }
  return (
    <Card>
      <h2 className="mb-3 flex items-center gap-2 text-lg font-extrabold text-navy"><Bot className="h-5 w-5 text-accent" />Campus Buddy</h2>
      <form onSubmit={ask} className="flex gap-2"><label htmlFor="mb" className="sr-only">Ask Campus Buddy</label>
        <input id="mb" className="field" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Aaj meri next class kaha hai?" />
        <Btn type="submit" variant="primary" loading={busy} aria-label="Ask"><Send className="h-4 w-4" /></Btn></form>
      {ans && <p className="clay-inset mt-3 p-3 text-sm text-ink">{ans.answer}</p>}
      <Link to="/app/buddy" className="mt-3 inline-block text-sm font-bold text-accent">Open full chat</Link>
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
            <MiniBuddy />
            <Card><h2 className="mb-3 flex items-center gap-2 text-lg font-extrabold text-navy"><ShieldCheck className="h-5 w-5 text-ok" />Timetable status</h2>
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

function StaffHome({ user }) {
  const s = useApi(api.summary, [])
  const mine = useApi(api.bookings, [], { enabled: user.role === 'club_representative' })
  return (
    <>
      <PageHeader title={`Hello, ${user.name.split(' ')[0]}`} subtitle="Live figures from the backend. Nothing on this page is hard-coded." />
      <Async state={s} rows={3}>{(d) => (
        <div className="grid gap-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat icon={CalendarCheck} tone="mint" label="Sessions scheduled" value={`${d.sessions_scheduled} / ${d.sessions_total}`} hint={`Timetable ${d.timetable_status}`} />
            <Stat icon={ShieldCheck} tone="lavender" label="Official validation" value={d.validation ? (d.validation.accepted ? 'Accepted' : 'Rejected') : 'Not run'} hint={d.validation ? `${d.validation.hard_violation_count} hard violations, soft ${d.validation.soft_total}` : ''} />
            <Stat icon={ClipboardCheck} tone="peach" label="Pending bookings" value={d.pending_bookings} hint={`${d.user_bookings} user request(s) total`} />
            <Stat icon={CalendarX2} tone="peri" label="Active disruptions" value={d.active_disruptions} hint={`${d.applied_disruptions} applied`} />
          </div>
          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <h2 className="mb-1 text-lg font-extrabold text-navy">Spectra week booking outcomes</h2><p className="mb-3 text-xs text-muted">Decisions made by the booking engine for the dataset's requests{d.booking_score != null ? `; validator booking score ${d.booking_score}` : ''}.</p>
              <div className="h-52"><ResponsiveContainer><BarChart data={[{ n: 'Approved', v: d.spectra.approved }, { n: 'Alternative', v: d.spectra.alternative }, { n: 'Rejected', v: d.spectra.rejected }]}>
                <XAxis dataKey="n" tick={{ fill: 'currentColor', fontSize: 12 }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fill: 'currentColor', fontSize: 12 }} axisLine={false} tickLine={false} width={28} /><Tooltip cursor={false} />
                <Bar dataKey="v" radius={[10, 10, 10, 10]}>{['#9ad9bf', '#b9a6ff', '#ffb3c6'].map((c) => <Cell key={c} fill={c} />)}</Bar></BarChart></ResponsiveContainer></div>
            </Card>
            <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Shortcuts</h2>
              <div className="grid gap-2.5">
                {user.role === 'admin' && <Link className="btn btn-primary" to="/app/generate"><Wand2 className="h-4 w-4" />Generate timetable</Link>}
                {user.role === 'admin' && <Link className="btn" to="/app/disruptions"><CalendarX2 className="h-4 w-4" />Preview a disruption</Link>}
                <Link className="btn" to="/app/bookings"><ClipboardCheck className="h-4 w-4" />Bookings</Link>
                <Link className="btn" to="/app/buddy"><Sparkles className="h-4 w-4" />Ask Campus Buddy</Link>
                <Link className="btn" to="/app/notifications"><Bell className="h-4 w-4" />Notifications</Link>
              </div></Card>
          </div>
          {user.role === 'club_representative' && <Card><h2 className="mb-3 text-lg font-extrabold text-navy">My requests</h2>
            <Async state={mine} rows={1} emptyIf={(x) => !x.count} empty={<Empty title="No requests yet" hint="Use Request a Venue to submit one." />}>{(m) => <ul className="grid gap-2">{m.bookings.slice(0, 5).map((b) => <li key={b.id} className="clay-sm flex items-center justify-between gap-3 p-3 text-sm"><span className="truncate font-bold text-navy">{b.request.title}</span><Pill tone={statusTone(b.state)}>{titleCase(b.state)}</Pill></li>)}</ul>}</Async></Card>}
        </div>)}</Async>
    </>
  )
}

export default function Overview() {
  const { user } = useAuth()
  return user.role === 'student' || user.role === 'faculty' ? <StudentFacultyHome user={user} /> : <StaffHome user={user} />
}
