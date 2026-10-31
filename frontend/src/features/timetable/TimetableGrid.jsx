import { useMemo } from 'react'
import { DAYS, DAY_NAMES, PERIOD_TIME, courseColor, periodEnd } from '../../utils/format'

const rowOf = (p) => (p <= 5 ? p + 1 : p + 2) // row 1 = header, row 7 = lunch
const PERIODS = [1, 2, 3, 4, 5, 6, 7, 8, 9]

function group(entries) {
  const m = new Map()
  for (const e of entries) {
    const k = `${e.day}|${e.start_period}|${e.end_period}`
    if (!m.has(k)) m.set(k, [])
    m.get(k).push(e)
  }
  return [...m.values()]
}

function Card({ list, onSelect, moved }) {
  const e = list[0]
  const multi = list.length > 1
  const isMoved = list.some((x) => moved?.has(x.session_id))
  return (
    <button onClick={() => onSelect(list)} aria-label={`${list.map((x) => x.course_title).join(', ')} ${DAY_NAMES[e.day]} ${PERIOD_TIME[e.start_period]}`}
      className={`clay-press z-10 m-0.5 flex min-w-0 flex-col justify-between overflow-hidden rounded-2xl p-2 text-left text-navy shadow-[3px_3px_8px_var(--sh-dark),-2px_-2px_6px_var(--sh-light),inset_1px_1px_3px_rgba(255,255,255,.6)] ${multi ? 'bg-surface' : courseColor(e.course_id)} ${isMoved ? 'ring-2 ring-warn' : ''}`}
      style={{ gridColumn: DAYS.indexOf(e.day) + 2, gridRow: `${rowOf(e.start_period)} / ${rowOf(e.end_period) + 1}` }}>
      {multi ? (
        <>
          <p className="text-[11px] font-extrabold uppercase tracking-wide text-accent">Elective basket</p>
          <ul className="space-y-0.5 text-[11px] font-semibold leading-tight">{list.map((x) => <li key={x.session_id} className="truncate">{x.course_id} &middot; {x.room_id}</li>)}</ul>
        </>
      ) : (
        <>
          <div><p className="truncate text-xs font-extrabold leading-tight sm:text-[13px]">{e.course_id}</p>
            <p className="truncate text-[11px] font-semibold opacity-80">{e.course_title}</p></div>
          <div className="mt-1 text-[11px] font-semibold leading-tight opacity-90"><p className="truncate">{e.room_id} &middot; {e.kind}</p><p className="hidden truncate sm:block">{e.faculty_name}</p></div>
        </>
      )}
    </button>
  )
}

/** Mon-Fri x P1-P9 grid with a distinct lunch row; multi-hour labs span rows; basket sessions stack in one card. */
export function TimetableGrid({ entries, onSelect, moved }) {
  const groups = useMemo(() => group(entries), [entries])
  return (
    <div className="clay-inset overflow-x-auto p-2 sm:p-3" role="region" aria-label="Weekly timetable grid" tabIndex={0}>
      <div className="grid min-w-[760px] gap-0" style={{ gridTemplateColumns: '78px repeat(5, minmax(130px, 1fr))', gridTemplateRows: '38px repeat(5, 76px) 30px repeat(4, 76px)' }}>
        <div style={{ gridColumn: 1, gridRow: 1 }} />
        {DAYS.map((d, i) => <div key={d} style={{ gridColumn: i + 2, gridRow: 1 }} className="grid place-items-center text-xs font-extrabold uppercase tracking-wide text-navy">{DAY_NAMES[d]}</div>)}
        {PERIODS.map((p) => (
          <div key={p} style={{ gridColumn: 1, gridRow: rowOf(p) }} className="flex flex-col items-center justify-center text-xs font-bold text-muted">
            <span className="text-navy">P{p}</span><span>{PERIOD_TIME[p]}</span></div>
        ))}
        <div style={{ gridColumn: '1 / -1', gridRow: 7 }} className="mx-1 my-1 grid place-items-center rounded-xl bg-peach/40 text-[11px] font-extrabold uppercase tracking-[.25em] text-[#6b3a14] dark:text-peach">Lunch &middot; 13:00-14:00</div>
        {PERIODS.flatMap((p) => DAYS.map((d, i) => <div key={`${d}${p}`} style={{ gridColumn: i + 2, gridRow: rowOf(p) }} className="m-0.5 rounded-2xl border border-[rgb(var(--peri)/.22)]" />))}
        {groups.map((l) => <Card key={l[0].session_id} list={l} onSelect={onSelect} moved={moved} />)}
      </div>
    </div>
  )
}

/** Compact day-by-day list for phones. */
export function Agenda({ entries, onSelect }) {
  return (
    <div className="grid gap-4">
      {DAYS.map((d) => {
        const l = group(entries.filter((e) => e.day === d)).sort((a, b) => a[0].start_period - b[0].start_period)
        return (
          <section key={d} aria-label={DAY_NAMES[d]}>
            <h3 className="mb-2 text-sm font-extrabold uppercase tracking-wide text-muted">{DAY_NAMES[d]}</h3>
            {l.length === 0 ? <p className="clay-inset px-4 py-3 text-sm text-muted">No classes</p> : (
              <ul className="grid gap-2">{l.map((g) => {
                const e = g[0]
                return (
                  <li key={e.session_id}><button onClick={() => onSelect(g)} className={`clay-sm clay-press flex w-full items-center gap-3 p-3 text-left`}>
                    <span className={`grid h-11 w-14 shrink-0 place-items-center rounded-xl text-xs font-extrabold text-navy ${g.length > 1 ? 'bg-surface' : courseColor(e.course_id)}`}>{PERIOD_TIME[e.start_period]}</span>
                    <span className="min-w-0"><span className="block truncate text-sm font-extrabold text-navy">{g.length > 1 ? `Elective basket (${g.length})` : `${e.course_id} \u00b7 ${e.course_title}`}</span>
                      <span className="block truncate text-xs text-muted">{PERIOD_TIME[e.start_period]}-{periodEnd(e.end_period)} &middot; {g.map((x) => x.room_id).join(', ')} &middot; {g[0].faculty_name}</span></span>
                  </button></li>
                )
              })}</ul>
            )}
          </section>
        )
      })}
    </div>
  )
}

/** Day view: rooms as columns, P1-P9 as rows (find a free room). */
export function RoomMatrix({ entries, day, rooms, onSelect }) {
  const cell = useMemo(() => { const m = {}; for (const e of entries.filter((x) => x.day === day)) for (let p = e.start_period; p <= e.end_period; p++) m[`${e.room_id}|${p}`] = e; return m }, [entries, day])
  return (
    <div className="clay-inset overflow-auto p-3" role="region" aria-label={`Room occupancy ${DAY_NAMES[day]}`} tabIndex={0}>
      <table className="border-separate border-spacing-1 text-xs">
        <thead><tr><th className="sticky left-0 bg-transparent px-2 text-muted">Room</th>{PERIODS.map((p) => <th key={p} className="px-2 py-1 text-center font-extrabold text-navy">P{p}<br /><span className="font-semibold text-muted">{PERIOD_TIME[p]}</span></th>)}</tr></thead>
        <tbody>{rooms.map((r) => (
          <tr key={r.id}><th scope="row" className="sticky left-0 z-10 whitespace-nowrap rounded-lg bg-surface px-2 py-1 text-left font-extrabold text-navy">{r.id}<span className="ml-1 font-semibold text-muted">{r.capacity}</span></th>
            {PERIODS.map((p) => { const e = cell[`${r.id}|${p}`]
              return <td key={p} className="p-0">{e ? <button onClick={() => onSelect([e])} className={`h-9 w-full min-w-[78px] truncate rounded-lg px-1.5 text-[11px] font-bold text-navy ${courseColor(e.course_id)}`}>{e.course_id}</button> : <div className="h-9 min-w-[78px] rounded-lg bg-mint/25" aria-label="free" />}</td> })}
          </tr>))}</tbody>
      </table>
    </div>
  )
}
