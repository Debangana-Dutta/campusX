import { useMemo } from 'react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../contexts/AppContexts'
import { Async, Card, Empty, PageHeader, Pill, Table } from '../components/ui'
import { DAY_NAMES, span, titleCase } from '../utils/format'

export default function Classes() {
  const { user } = useAuth()
  const tt = useApi(api.timetable, [])
  const mine = useMemo(() => (tt.data?.sessions || []).filter((e) => e.faculty_id === user.faculty_id), [tt.data, user])
  const courses = [...new Set(mine.map((e) => e.course_id))]
  return (
    <>
      <PageHeader title="My Classes" subtitle={`Every session you teach (${user.faculty_id}), with room, groups and size.`} />
      <Async state={tt} rows={2}>{() => mine.length === 0 ? <Empty title="No classes assigned" /> : (
        <div className="grid gap-5"><Card><p className="text-sm text-muted">{mine.length} session(s) across {courses.length} course(s); {mine.reduce((s, e) => s + e.end_period - e.start_period + 1, 0)} teaching hours a week.</p></Card>
          <Table head={['Course', 'Type', 'When', 'Room', 'Groups', 'Students']}>{[...mine].sort((a, b) => a.course_id.localeCompare(b.course_id)).map((e) => <tr key={e.session_id}><td className="td font-bold text-navy">{e.course_id}<br /><span className="font-normal text-muted">{e.course_title}</span></td><td className="td"><Pill tone="lav">{titleCase(e.kind)}</Pill></td><td className="td whitespace-nowrap">{DAY_NAMES[e.day]} {span(e.start_period, e.end_period)}</td><td className="td">{e.room_id}</td><td className="td">{e.groups.join(', ')}</td><td className="td">{e.size}</td></tr>)}</Table></div>)}</Async>
    </>
  )
}
