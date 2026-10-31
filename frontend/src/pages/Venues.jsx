import { useMemo, useState } from 'react'
import { Accessibility, Building2, Users, Wrench } from 'lucide-react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { Async, Card, Empty, Field, PageHeader, Pill } from '../components/ui'
import { DAYS, DAY_NAMES, PERIOD_TIME, titleCase } from '../utils/format'

const FEATS = ['projector', 'pa_system', 'stage', 'computers', 'ac', 'power_benches']

export default function Venues() {
  const v = useApi(api.venues, [])
  const tt = useApi(api.timetable, [])
  const [f, setF] = useState({ type: '', cap: '', acc: false, feats: [], day: '', period: '' })
  const busy = useMemo(() => {   // (room|day|period) occupied by classes, from the real generated timetable
    const m = new Set(); for (const e of tt.data?.sessions || []) for (let p = e.start_period; p <= e.end_period; p++) m.add(`${e.room_id}|${e.day}|${p}`); return m
  }, [tt.data])
  const rooms = (v.data?.rooms || []).filter((r) => {
    if (f.type && r.type !== f.type) return false
    if (f.cap && r.capacity < +f.cap) return false
    if (f.acc && !r.accessible) return false
    if (f.feats.some((x) => !r.features.includes(x))) return false
    if (f.day && f.period) {
      const p = +f.period
      if (busy.has(`${r.id}|${f.day}|${p}`)) return false
      if (r.closures.some((c) => c.day === f.day && c.periods.includes(p))) return false
      if (r.bookings.some((b) => b.day === f.day && b.from <= p && p <= b.to)) return false
    }
    return true
  })
  const types = [...new Set((v.data?.rooms || []).map((r) => r.type))]
  const toggle = (x) => setF((s) => ({ ...s, feats: s.feats.includes(x) ? s.feats.filter((y) => y !== x) : [...s.feats, x] }))
  return (
    <>
      <PageHeader title="Venues" subtitle="Room directory from the dataset with real closures, Spectra bookings and teaching load. 'Free at' checks classes, closures and bookings." />
      <Card className="mb-5 grid gap-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Room type" id="vt"><select id="vt" className="field" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="">Any</option>{types.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}</select></Field>
          <Field label="Min. capacity" id="vc"><input id="vc" type="number" min="0" className="field" value={f.cap} onChange={(e) => setF({ ...f, cap: e.target.value })} placeholder="e.g. 100" /></Field>
          <Field label="Free on" id="vd"><select id="vd" className="field" value={f.day} onChange={(e) => setF({ ...f, day: e.target.value })}><option value="">Any day</option>{DAYS.map((d) => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}</select></Field>
          <Field label="At period" id="vp"><select id="vp" className="field" value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })}><option value="">Any</option>{Object.entries(PERIOD_TIME).filter(([p]) => +p <= 9).map(([p, t]) => <option key={p} value={p}>P{p} ({t})</option>)}</select></Field>
          <label className="flex items-end gap-2 pb-3 text-sm font-bold text-navy"><input type="checkbox" checked={f.acc} onChange={(e) => setF({ ...f, acc: e.target.checked })} />Accessible only</label>
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Required features">{FEATS.map((x) => <button key={x} aria-pressed={f.feats.includes(x)} onClick={() => toggle(x)} className={`pill ${f.feats.includes(x) ? 'bg-lavender/80 text-navy' : 'bg-surface text-muted'}`}>{titleCase(x)}</button>)}</div>
      </Card>
      <Async state={v} rows={3}>{() => (
        <div className="grid gap-5">
          {rooms.length === 0 ? <Empty icon={Building2} title="No rooms match these filters" hint="Relax a filter or change the day/period." /> : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{rooms.map((r) => (
              <Card key={r.id} className="!p-4">
                <div className="flex items-start justify-between gap-2"><div><p className="text-lg font-extrabold text-navy">{r.id}</p><p className="text-xs text-muted">{r.name} &middot; {titleCase(r.type)}</p></div>
                  <div className="flex gap-1.5"><Pill tone="info"><Users className="h-3 w-3" />{r.capacity}</Pill>{r.accessible && <Pill tone="ok"><Accessibility className="h-3 w-3" />Accessible</Pill>}</div></div>
                <div className="mt-2 flex flex-wrap gap-1.5">{r.features.map((x) => <Pill key={x} tone="lav">{titleCase(x)}</Pill>)}</div>
                <p className="mt-2 text-xs text-muted">Allowed uses: {r.allowed_uses.join(', ')} &middot; {r.teaching_hours} teaching h/week</p>
                {r.closures.map((c, i) => <p key={i} className="mt-2 flex items-start gap-1.5 rounded-xl bg-peach/50 px-2.5 py-1.5 text-xs font-semibold text-[#6b3a14] dark:text-peach"><Wrench className="mt-0.5 h-3.5 w-3.5 shrink-0" />{c.reason || 'Closed'}: {c.day} P{c.periods[0]}-P{c.periods.at(-1)}</p>)}
                {r.bookings.length > 0 && <ul className="mt-2 grid gap-1">{r.bookings.map((b) => <li key={b.request_id} className="truncate rounded-xl bg-peri/40 px-2.5 py-1 text-xs font-semibold text-navy">{b.title} &middot; {b.day} P{b.from}-P{b.to}</li>)}</ul>}
              </Card>))}</div>)}
          <Card><h2 className="mb-1 text-lg font-extrabold text-navy">Weekly teaching hours by room</h2><p className="mb-3 text-xs text-muted">From the generated timetable (45 teaching periods per room per week).</p>
            <div className="h-64"><ResponsiveContainer><BarChart data={[...v.data.rooms].sort((a, b) => b.teaching_hours - a.teaching_hours).slice(0, 15).map((r) => ({ n: r.id, h: r.teaching_hours }))}>
              <XAxis dataKey="n" tick={{ fill: 'currentColor', fontSize: 11 }} axisLine={false} tickLine={false} interval={0} angle={-35} textAnchor="end" height={55} /><YAxis tick={{ fill: 'currentColor', fontSize: 11 }} axisLine={false} tickLine={false} width={28} /><Tooltip cursor={false} />
              <Bar dataKey="h" name="Hours" fill="#b9a6ff" radius={[8, 8, 8, 8]} /></BarChart></ResponsiveContainer></div></Card>
        </div>)}</Async>
    </>
  )
}
