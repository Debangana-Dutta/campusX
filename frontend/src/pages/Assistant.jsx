import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, Send } from 'lucide-react'
import { api } from '../services/api'
import { useToast } from '../contexts/AppContexts'
import { Btn, Card, Empty, PageHeader, Pill } from '../components/ui'
import { DAY_NAMES, PERIOD_TIME } from '../utils/format'

const PROMPTS = ['I am unavailable on Wednesday because I have to attend a conference.', 'I am on leave tomorrow. Find alternative slots for all my classes.', 'Move my Data Structures lecture from Monday P2 to Tuesday P3.', 'The room assigned to my lab is unavailable. Find another suitable laboratory.']
const slot = (a) => `${DAY_NAMES[a.day]} P${a.start_period} (${PERIOD_TIME[a.start_period]}) · ${a.room_id}`

export default function Assistant() {
  const toast = useToast()
  const [text, setText] = useState('')
  const [sent, setSent] = useState('')
  const [res, setRes] = useState(null)
  const [choices, setChoices] = useState({})
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)
  const [error, setError] = useState('')

  const run = async (t, ch = {}) => {
    setBusy(true); setDone(null); setError('')
    try { setRes(await api.assistantDraft(t, ch)); setSent(t); setChoices(ch) } catch (e) { setRes(null); setError(e.message); toast(e.message, 'error') } finally { setBusy(false) }
  }
  const submit = async () => {
    setBusy(true)
    try { setDone(await api.assistantSubmit(sent, choices)); toast('Submitted for Admin approval', 'ok') } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  const p = res?.proposal
  return (
    <>
      <PageHeader title="Schedule Assistant" subtitle="Describe the change you need. Every option is checked against all scheduling rules and the official validator. Nothing changes until an Admin approves it." />
      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="grid h-fit gap-3 lg:col-span-2">
          <form onSubmit={(e) => { e.preventDefault(); if (text.trim().length >= 5) run(text.trim()) }} className="grid gap-3" aria-label="Schedule request">
            <label htmlFor="sa" className="label">What do you need?</label>
            <textarea id="sa" rows={4} className="field" value={text} onChange={(e) => setText(e.target.value)} maxLength={600} placeholder="e.g. I am unavailable on Wednesday because of a conference" />
            <Btn type="submit" variant="primary" loading={busy && !done} disabled={text.trim().length < 5}><Send className="h-4 w-4" />Find options</Btn>
          </form>
          <div><p className="label">Examples</p><div className="flex flex-wrap gap-2">{PROMPTS.map((x) => <button key={x} type="button" onClick={() => setText(x)} className="pill tone-neutral text-left hover:text-navy">{x.length > 52 ? `${x.slice(0, 52)}…` : x}</button>)}</div></div>
          <p className="text-xs text-muted">Extra tutorials and swapping a room in the same slot with a different lab are not supported yet.</p>
        </Card>

        <div className="grid gap-5 lg:col-span-3">
          {error && <Card role="alert"><p className="mb-1 flex items-center gap-2 font-bold text-navy"><AlertTriangle className="h-5 w-5 text-warning" />The assistant could not process this request</p><p className="text-sm text-ink">{error}</p></Card>}
          {!res && !error ? <Empty title="No request yet" hint="Describe a change and the assistant will show valid alternatives, or explain why none exist." /> : !res ? null : (
            <>
              {res.status === 'nothing_to_move' && <Card role="status"><p className="mb-1 flex items-center gap-2 font-bold text-navy"><Info className="h-5 w-5" />Nothing needs to move</p><p className="text-sm text-ink">{res.message}</p></Card>}
              {res.status === 'not_supported' && <Card role="status"><p className="mb-1 flex items-center gap-2 font-bold text-navy"><Info className="h-5 w-5" />This assistant can't do that yet</p><p className="text-sm text-ink">{res.message}</p></Card>}
              {res.status === 'needs_info' && res.follow_up?.length > 0 && <Card role="status"><p className="mb-1 font-bold text-navy">I need a bit more information</p><ul className="list-disc pl-5 text-sm text-ink">{res.follow_up.map((q) => <li key={q}>{q}</li>)}</ul></Card>}
              {Object.entries(res.alternatives || {}).map(([sid, alts]) => (
                <Card key={sid}><h2 className="mb-2 text-lg font-bold text-navy">{sid}</h2>
                  <fieldset className="grid gap-2"><legend className="sr-only">Options for {sid}</legend>
                    {alts.map((a, i) => (
                      <label key={i} className="clay-sm flex cursor-pointer items-start gap-3 p-3 text-sm">
                        <input type="radio" name={`alt-${sid}`} className="mt-1" checked={(choices[sid] ?? 0) === i} onChange={() => run(sent, { ...choices, [sid]: i })} />
                        <span><b className="text-navy">{slot(a)}</b><span className="mt-0.5 block text-xs text-muted">{a.explanation.join(' ')}</span></span></label>))}
                  </fieldset></Card>))}
              {res.no_solution?.map((n, i) => (
                <Card key={i} role="alert"><p className="mb-1 flex items-center gap-2 font-bold text-navy"><AlertTriangle className="h-5 w-5 text-warning" />{n.session_id}: {n.asked ? `${n.asked} cannot be used` : 'no valid alternative'}</p>
                  <p className="text-sm text-ink">{n.why_not}</p>
                  {n.removed_by_hard_rules && <p className="mt-2 text-xs text-muted">Slots ruled out by hard rules: {Object.entries(n.removed_by_hard_rules).map(([k, v]) => `${k.replace(/_/g, ' ')} ×${v}`).join(', ')}. Clashes with other bookings/classes: {Object.entries(n.rejected_slots_by_constraint || {}).map(([k, v]) => `${k} ×${v}`).join(', ') || 'none'}.</p>}
                  {n.other_options?.length > 0 && <p className="mt-2 text-sm text-muted">Other valid options: {n.other_options.map(slot).join(' · ')}</p>}</Card>))}
              {p && (
                <Card><div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-bold text-navy">Proposal</h2>
                  <Pill tone={p.feasible ? 'ok' : 'bad'}><CheckCircle2 className="h-3.5 w-3.5" />Official validator: {p.feasible ? 'accepted' : 'rejected'}</Pill><Pill>{p.moved.length} session(s) move</Pill></div>
                  {!p.feasible && <ul className="mt-2 list-disc pl-5 text-sm text-ink">{p.rejected_by_validator?.map((x) => <li key={x}>{x}</li>)}</ul>}
                  <ul className="mt-3 grid gap-1.5 text-sm">{p.moved.map((m) => <li key={m.session_id} className="clay-inset px-3 py-2"><b className="text-navy">{m.session_id}</b> {DAY_NAMES[m.from.day]} P{m.from.start_period} {m.from.room_id} → {DAY_NAMES[m.to.day]} P{m.to.start_period} {m.to.room_id} <span className="text-muted">({m.reason})</span></li>)}</ul>
                  {done ? <p role="status" className="tone-ok mt-4 rounded-xl px-3 py-2 text-sm font-semibold">{done.message} Reference {done.id}.</p>
                    : <Btn variant="mint" className="mt-4" loading={busy} disabled={!p.feasible} onClick={submit}>Submit for Admin approval</Btn>}
                  <p className="mt-2 text-xs text-muted">The timetable stays unchanged until the Admin approves this request.</p></Card>)}
            </>)}
        </div>
      </div>
    </>
  )
}
