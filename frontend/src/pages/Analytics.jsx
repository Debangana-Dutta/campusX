import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { Async, Card, PageHeader, Pill } from '../components/ui'

const C = ['#b9a6ff', '#9ad9bf', '#ffc4a3', '#9fb2ff', '#a8d8f5', '#ffb3c6']
const ax = { tick: { fill: 'currentColor', fontSize: 11 }, axisLine: false, tickLine: false }
function Chart({ title, note, children, h = 260 }) { return <Card><h2 className="text-lg font-extrabold text-navy">{title}</h2><p className="mb-3 text-xs text-muted">{note}</p><div style={{ height: h }}><ResponsiveContainer>{children}</ResponsiveContainer></div></Card> }

export default function Analytics() {
  const a = useApi(api.analytics, [])
  const u = useApi(api.utilisation, [])
  return (
    <>
      <PageHeader title="Room Usage" subtitle="Figures come from the current timetable, exams and bookings." />
      <Async state={a} rows={3}>{(d) => (
        <div className="grid gap-5 lg:grid-cols-2">
          <Chart title="Room utilisation (teaching hours)" note="Share of available teaching periods used per room. Rooms with closures have fewer available periods.">
            <BarChart data={(u.data?.rooms || []).slice(0, 14).map((r) => ({ n: r.room_id, pct: r.utilisation_pct }))}><CartesianGrid vertical={false} strokeOpacity={.15} /><XAxis dataKey="n" {...ax} interval={0} angle={-35} textAnchor="end" height={50} /><YAxis {...ax} width={34} unit="%" /><Tooltip cursor={false} /><Bar dataKey="pct" name="Utilisation %" fill="#b9a6ff" radius={[8, 8, 8, 8]} /></BarChart></Chart>
          <Chart title="Sessions per day" note="Number of scheduled sessions each weekday.">
            <BarChart data={d.sessions_per_day}><CartesianGrid vertical={false} strokeOpacity={.15} /><XAxis dataKey="day" {...ax} /><YAxis {...ax} width={30} /><Tooltip cursor={false} /><Bar dataKey="sessions" fill="#9ad9bf" radius={[8, 8, 8, 8]} /></BarChart></Chart>
          <Chart title="Faculty workload (top 15)" note="Weekly teaching hours; daily limit is 4 hours.">
            <BarChart data={d.faculty_workload} layout="vertical"><CartesianGrid horizontal={false} strokeOpacity={.15} /><XAxis type="number" {...ax} /><YAxis type="category" dataKey="faculty_id" {...ax} width={36} /><Tooltip cursor={false} /><Bar dataKey="hours" fill="#9fb2ff" radius={[8, 8, 8, 8]} /></BarChart></Chart>
          <Card><h2 className="text-lg font-extrabold text-navy">Session types</h2><p className="mb-3 text-xs text-muted">Lectures, tutorials and labs in the timetable.</p>
            <div className="h-60"><ResponsiveContainer><PieChart><Pie data={Object.entries(d.session_kinds).map(([name, value]) => ({ name, value }))} dataKey="value" innerRadius={55} outerRadius={90} paddingAngle={4}>{Object.keys(d.session_kinds).map((k, i) => <Cell key={k} fill={C[i]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>
            <div className="flex flex-wrap gap-2">{Object.entries(d.session_kinds).map(([k, v], i) => <Pill key={k} tone="neutral"><span className="h-2.5 w-2.5 rounded-full" style={{ background: C[i] }} />{k}: {v}</Pill>)}</div></Card>
          <Chart title="Exam rooms used per slot" note="Rooms allocated in each exam slot (an exam can use several)." h={240}>
            <BarChart data={d.exam_rooms_per_slot}><CartesianGrid vertical={false} strokeOpacity={.15} /><XAxis dataKey="slot" {...ax} /><YAxis {...ax} width={30} /><Tooltip cursor={false} /><Bar dataKey="rooms_used" fill="#ffc4a3" radius={[8, 8, 8, 8]} /></BarChart></Chart>
          <Card className="self-start"><h2 className="text-lg font-extrabold text-navy">Data origin</h2><p className="mt-2 text-sm text-muted">{d.data_origin}. Spectra booking outcomes are on the Overview page.</p></Card>
        </div>)}</Async>
    </>
  )
}
