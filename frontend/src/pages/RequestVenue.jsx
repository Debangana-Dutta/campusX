import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Bot, Languages, Send, Wand2 } from 'lucide-react'
import { api } from '../services/api'
import { useAuth, useToast } from '../contexts/AppContexts'
import { Btn, Card, Field, PageHeader, Pill, statusTone } from '../components/ui'
import { DAYS, DAY_NAMES, PERIOD_TIME, titleCase } from '../utils/format'

const TYPES = ['classroom', 'lecture_hall', 'auditorium', 'seminar_hall', 'outdoor', 'lab_cs', 'lab_elec', 'lab_phy', 'workshop', 'lab_civil']
const NEEDS = ['accessible', 'computers', 'pa_system', 'projector', 'stage', 'ac', 'power_benches']
const CATS = ['institute_event', 'guest_lecture', 'department_event', 'club_event']
const CAP = { admin: 0, faculty: 1, department_coordinator: 2, club_representative: 3 }   // lowest allowed category index (role cap)
const SAMPLES = ['Need a room for 45 people on Tuesday 6 to 8 pm, projector please.', 'Seminar hall kal shaam 6 baje, 2 ghante, 100 log, mic chahiye', 'Lab with computers for a 3-hour coding contest on Thursday afternoon, about 60 participants']
const empty = { title: '', attendance: '', duration_periods: '', day: 'TUE', from_period: 10, to_period: 11, room_types: ['classroom', 'lecture_hall', 'seminar_hall'], needs: [], requested_room: '', mandatory_for_groups: '', requested_category: 'club_event', department: '', raw_text: '' }

export default function RequestVenue() {
  const { user } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const [text, setText] = useState('')
  const [parse, setParse] = useState(null)
  const [busy, setBusy] = useState(false)
  const [f, setF] = useState({ ...empty, requested_category: CATS[CAP[user.role]], department: user.department || '' })
  const [errs, setErrs] = useState({})
  const [result, setResult] = useState(null)
  const cats = CATS.slice(CAP[user.role])
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }))
  const tog = (k, x) => setF((s) => ({ ...s, [k]: s[k].includes(x) ? s[k].filter((y) => y !== x) : [...s[k], x] }))

  const doParse = async () => {
    if (text.trim().length < 5) return toast('Describe your request first (English or Hinglish)', 'error')
    setBusy(true)
    try {
      const r = await api.parseBooking(text); setParse(r)
      const x = r.fields; const w = x.windows?.[0]
      setF((s) => ({ ...s, title: x.title || s.title, attendance: x.attendance ?? '', duration_periods: x.duration_periods ?? '', day: w?.day || s.day, from_period: w?.from_period ?? s.from_period, to_period: w?.to_period ?? s.to_period,
        room_types: x.room_types || s.room_types, needs: x.needs || [], requested_room: x.requested_room || '', mandatory_for_groups: (x.mandatory_for_groups || []).join(', '),
        requested_category: cats.includes(x.requested_category) ? x.requested_category : cats[cats.length - 1], raw_text: text }))
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  const validate = () => {
    const e = {}
    if (f.title.trim().length < 3) e.title = 'Give the event a title (3+ characters)'
    if (!(+f.attendance >= 1)) e.attendance = 'Enter the expected attendance'
    if (!(+f.duration_periods >= 1)) e.duration = 'Enter the duration in hours'
    if (+f.to_period < +f.from_period) e.window = 'The window must end after it starts'
    else if (+f.duration_periods > +f.to_period - +f.from_period + 1) e.duration = `The window is ${+f.to_period - +f.from_period + 1} period(s) long; widen it or shorten the event`
    if (!f.room_types.length) e.types = 'Pick at least one venue type'
    setErrs(e); return !Object.keys(e).length
  }
  const submit = async (ev) => {
    ev.preventDefault(); if (!validate()) return toast('Please fix the highlighted fields', 'error')
    setBusy(true)
    try {
      const r = await api.createBooking({ title: f.title.trim(), attendance: +f.attendance, duration_periods: +f.duration_periods, windows: [{ day: f.day, from_period: +f.from_period, to_period: +f.to_period }],
        room_types: f.room_types, needs: f.needs, requested_room: f.requested_room.trim() || null, mandatory_for_groups: f.mandatory_for_groups.split(/[ ,]+/).filter(Boolean),
        requested_category: f.requested_category, department: f.department || null, raw_text: f.raw_text || text })
      setResult(r); toast(`Decision: ${titleCase(r.decision.status)}`, r.decision.status === 'rejected' ? 'error' : 'ok')
    } catch (e) { toast(e.message, 'error'); if (e.detail?.needs_clarification) setErrs({ duration: e.message }) } finally { setBusy(false) }
  }
  const P = Object.entries(PERIOD_TIME)
  return (
    <>
      <PageHeader title={user.role === 'department_coordinator' ? 'Book a Room' : 'Request a Venue'} subtitle="Describe the event in your own words, review what was understood, edit anything, then submit. The booking engine (not AI) makes the decision." />
      <div className="grid gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-2">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-extrabold text-navy"><Languages className="h-5 w-5 text-accent" />1. Tell us what you need</h2>
          <label htmlFor="nl" className="label">Your request (English or Hinglish)</label>
          <textarea id="nl" rows={5} className="field" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Seminar hall kal shaam 6 baje, 2 ghante, 100 log, mic chahiye" />
          <div className="mt-3 flex flex-wrap gap-2">{SAMPLES.map((s) => <button key={s} onClick={() => setText(s)} className="pill bg-surface text-left text-muted hover:text-navy">{s.length > 38 ? `${s.slice(0, 38)}...` : s}</button>)}</div>
          <Btn variant="primary" className="mt-4 w-full" loading={busy} onClick={doParse}><Wand2 className="h-4 w-4" />Understand my request</Btn>
          {parse && (
            <div className="mt-4 grid gap-3 text-sm" role="status">
              <Pill tone={parse.ai_used ? 'lav' : 'neutral'}><Bot className="h-3 w-3" />{parse.ai_used ? 'Read with Gemini (validated by the backend)' : 'Read with built-in rules'}</Pill>
              {parse.ai_error && !parse.ai_used && <p className="text-xs text-muted">{parse.ai_error}.</p>}
              {parse.follow_up?.length > 0 && <div className="clay-inset p-3"><p className="mb-1 font-extrabold text-navy">I need a bit more information:</p><ul className="list-disc pl-5 text-ink">{parse.follow_up.map((q) => <li key={q}>{q}</li>)}</ul></div>}
              {parse.assumptions?.length > 0 && <div className="clay-inset p-3"><p className="mb-1 font-extrabold text-navy">Please confirm my assumptions:</p><ul className="list-disc pl-5 text-ink">{parse.assumptions.map((q) => <li key={q}>{q}</li>)}</ul></div>}
              {parse.warnings?.map((w) => <p key={w} className="flex gap-2 rounded-xl bg-peach/50 p-3 font-semibold text-[#6b3a14] dark:text-peach"><AlertTriangle className="h-4 w-4 shrink-0" />{w}</p>)}
            </div>)}
          <p className="mt-4 text-xs text-muted">No AI available? The form on the right always works on its own.</p>
        </Card>

        <Card as="form" onSubmit={submit} noValidate className="grid gap-4 xl:col-span-3" aria-label="Booking details">
          <h2 className="text-lg font-extrabold text-navy">2. Review and edit, then submit</h2>
          <Field label="Event title" id="t"><input id="t" className="field" value={f.title} onChange={(e) => set('title', e.target.value)} aria-invalid={!!errs.title} />{errs.title && <p className="mt-1 text-xs font-bold text-bad">{errs.title}</p>}</Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Attendance" id="a"><input id="a" type="number" min="1" className="field" value={f.attendance} onChange={(e) => set('attendance', e.target.value)} />{errs.attendance && <p className="mt-1 text-xs font-bold text-bad">{errs.attendance}</p>}</Field>
            <Field label="Duration (hours)" id="d"><input id="d" type="number" min="1" max="13" className="field" value={f.duration_periods} onChange={(e) => set('duration_periods', e.target.value)} />{errs.duration && <p className="mt-1 text-xs font-bold text-bad">{errs.duration}</p>}</Field>
            <Field label="Category" id="c" hint={`Your role caps this at ${titleCase(cats[0])}.`}><select id="c" className="field" value={f.requested_category} onChange={(e) => set('requested_category', e.target.value)}>{cats.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}</select></Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Day" id="day"><select id="day" className="field" value={f.day} onChange={(e) => set('day', e.target.value)}>{DAYS.map((d) => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}</select></Field>
            <Field label="Window starts" id="f"><select id="f" className="field" value={f.from_period} onChange={(e) => set('from_period', +e.target.value)}>{P.map(([p, t]) => <option key={p} value={p}>P{p} ({t})</option>)}</select></Field>
            <Field label="Window ends (period)" id="to"><select id="to" className="field" value={f.to_period} onChange={(e) => set('to_period', +e.target.value)}>{P.map(([p, t]) => <option key={p} value={p}>P{p} (ends {String(+t.slice(0, 2) + 1).padStart(2, '0')}:00)</option>)}</select>{errs.window && <p className="mt-1 text-xs font-bold text-bad">{errs.window}</p>}</Field>
          </div>
          <fieldset><legend className="label">Venue types</legend><div className="flex flex-wrap gap-2">{TYPES.map((t) => <button type="button" key={t} aria-pressed={f.room_types.includes(t)} onClick={() => tog('room_types', t)} className={`pill ${f.room_types.includes(t) ? 'bg-lavender/80 text-navy' : 'bg-surface text-muted'}`}>{titleCase(t)}</button>)}</div>{errs.types && <p className="mt-1 text-xs font-bold text-bad">{errs.types}</p>}</fieldset>
          <fieldset><legend className="label">Required features</legend><div className="flex flex-wrap gap-2">{NEEDS.map((t) => <button type="button" key={t} aria-pressed={f.needs.includes(t)} onClick={() => tog('needs', t)} className={`pill ${f.needs.includes(t) ? 'bg-mint/80 text-[#14513f]' : 'bg-surface text-muted'}`}>{titleCase(t)}</button>)}</div></fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Preferred room (optional)" id="rr" hint="Only a wish: the engine may suggest another room that meets your needs."><input id="rr" className="field" value={f.requested_room} onChange={(e) => set('requested_room', e.target.value.toUpperCase())} placeholder="e.g. SH-1" /></Field>
            <Field label="Mandatory student groups (optional)" id="mg" hint="Comma separated, e.g. CSE-3"><input id="mg" className="field" value={f.mandatory_for_groups} onChange={(e) => set('mandatory_for_groups', e.target.value.toUpperCase())} /></Field>
          </div>
          <Btn type="submit" variant="primary" loading={busy} className="w-full sm:w-fit"><Send className="h-4 w-4" />Submit for decision</Btn>
        </Card>
      </div>
      {result && (
        <Card className="mt-5" role="status">
          <div className="flex flex-wrap items-center gap-3"><h2 className="text-lg font-extrabold text-navy">{result.id}</h2><Pill tone={statusTone(result.decision.status)}>{titleCase(result.decision.status)}</Pill><Pill tone={statusTone(result.state)}>{titleCase(result.state)}</Pill></div>
          <p className="mt-3 text-sm text-ink">{result.decision.reason}</p>
          {result.decision.room_id && <p className="mt-2 text-sm font-bold text-navy">{result.decision.room_id} &middot; {DAY_NAMES[result.decision.day]} P{result.decision.start_period}-P{result.decision.end_period}</p>}
          {result.decision.needs_approval && <p className="mt-2 text-sm text-muted">Waiting for approval: {result.decision.needs_approval}.</p>}
          <div className="mt-4 flex gap-2"><Btn variant="primary" onClick={() => nav('/app/bookings')}>Open my bookings</Btn><Btn onClick={() => { setResult(null); setParse(null); setText('') }}>New request</Btn></div>
        </Card>)}
    </>
  )
}
