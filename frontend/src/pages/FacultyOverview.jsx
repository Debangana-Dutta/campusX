import { useMemo } from 'react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../contexts/AppContexts'
import { Async, PageHeader, Pill, Table } from '../components/ui'
import { DAYS } from '../utils/format'

export default function FacultyOverview() {
  const { user } = useAuth()
  const tt = useApi(api.timetable, [])
  const ds = useApi(api.datasetSummary, [])
  const rows = useMemo(() => {
    const fac = (ds.data?.faculty || []).filter((f) => user.role === 'admin' || f.department === user.department)
    return fac.map((f) => { const s = (tt.data?.sessions || []).filter((e) => e.faculty_id === f.id); const perDay = Object.fromEntries(DAYS.map((d) => [d, s.filter((e) => e.day === d).reduce((a, e) => a + e.end_period - e.start_period + 1, 0)]))
      return { ...f, hours: Object.values(perDay).reduce((a, b) => a + b, 0), perDay, courses: [...new Set(s.map((e) => e.course_id))] } })
  }, [tt.data, ds.data, user])
  return (
    <>
      <PageHeader title="Faculty Overview" subtitle={user.role === 'admin' ? 'All faculty.' : `Faculty of ${user.department}.`} />
      <Async state={{ ...tt, loading: tt.loading || ds.loading, error: tt.error || ds.error, reload: tt.reload }} rows={2}>{() => (
        <Table head={['Faculty', 'Hours / week', ...DAYS, 'Courses']}>{rows.map((r) => <tr key={r.id}><td className="td font-bold text-navy">{r.name}<br /><span className="font-normal text-muted">{r.id} &middot; {r.department}</span></td><td className="td">{r.hours}</td>
          {DAYS.map((d) => <td key={d} className="td"><Pill tone={r.perDay[d] >= 4 ? 'warn' : r.perDay[d] ? 'info' : 'neutral'}>{r.perDay[d]}h</Pill></td>)}<td className="td">{r.courses.join(', ') || '-'}</td></tr>)}</Table>)}</Async>
    </>
  )
}
