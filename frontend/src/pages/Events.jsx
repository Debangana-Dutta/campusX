import { PartyPopper } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { Async, Card, Empty, PageHeader, Pill } from '../components/ui'
import { DAY_NAMES, DAYS, span, titleCase } from '../utils/format'

export default function Events() {
  const e = useApi(api.events, [])
  return (
    <>
      <PageHeader title="Campus Events" subtitle="Approved and confirmed venue bookings, by day." />
      <Async state={e} rows={3} emptyIf={(d) => !d.events.length} empty={<Empty icon={PartyPopper} title="No events yet" hint="Approved bookings will appear here." />}>{(d) => (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{DAYS.map((day) => { const l = d.events.filter((x) => x.day === day); return (
          <Card key={day}><h2 className="mb-3 text-lg font-extrabold text-navy">{DAY_NAMES[day]}</h2>
            {l.length === 0 ? <p className="text-sm text-muted">No events.</p> : <ul className="grid gap-2.5">{l.map((x) => <li key={x.id} className="clay-sm p-3"><p className="text-sm font-extrabold text-navy">{x.title}</p><p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">{span(x.from, x.to)} &middot; {x.room_id}<Pill tone="lav">{titleCase(x.category)}</Pill></p></li>)}</ul>}</Card>) })}</div>)}</Async>
    </>
  )
}
