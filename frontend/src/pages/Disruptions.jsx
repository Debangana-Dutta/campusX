import { useRef, useState } from 'react'
import { ArrowRight, FileUp, Play, ShieldCheck, Stamp } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useToast } from '../contexts/AppContexts'
import { Btn, Card, Empty, Modal, PageHeader, Pill, Table, statusTone } from '../components/ui'
import { DAY_NAMES, titleCase } from '../utils/format'

const TYPES = ['faculty_unavailable', 'room_unavailable', 'add_faculty', 'add_session', 'remove_session']
const describe = (c) => ({
  faculty_unavailable: `Faculty ${c.faculty_id} unavailable ${c.days?.join('/')} P${c.periods?.[0]}-P${c.periods?.at(-1)}${c.reason ? ` (${c.reason})` : ''}`,
  room_unavailable: `Room ${c.room_id} closed ${c.days?.join('/')} P${c.periods?.[0]}-P${c.periods?.at(-1)}${c.reason ? ` (${c.reason})` : ''}`,
  add_faculty: `New faculty ${c.faculty?.id} ${c.faculty?.name || ''}`, add_session: `New session ${c.session?.id} (${c.session?.kind}, ${c.session?.duration}h)`, remove_session: `Remove session ${c.session_id}`,
}[c.type] || `Unknown change type "${c.type}"`)
const Slot = ({ s, tone }) => <div className={`rounded-xl px-3 py-2 text-xs font-bold text-navy ${tone}`}>{DAY_NAMES[s.day]} P{s.start_period}<br />{s.room_id}</div>
const FLOW = ['Preview', 'Validate', 'Admin review', 'Approve', 'Apply']

export default function Disruptions() {
  const toast = useToast()
  const hist = useApi(api.disruptions, [])
  const [text, setText] = useState('')
  const [changes, setChanges] = useState(null)
  const [limit, setLimit] = useState(90)
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const [confirm, setConfirm] = useState(false)
  const [applied, setApplied] = useState(false)
  const file = useRef(null)

  const load = (raw) => {
    try {
      const j = JSON.parse(raw)
      if (!Array.isArray(j.changes) || !j.changes.length) throw new Error('The file needs a non-empty "changes" array')
      const bad = j.changes.find((c) => !TYPES.includes(c.type))
      if (bad) throw new Error(`Unknown change type "${bad.type}". Allowed: ${TYPES.join(', ')}`)
      setChanges(j.changes); setText(JSON.stringify(j, null, 2)); setRes(null); setApplied(false)
    } catch (e) { setChanges(null); toast(`Invalid change file: ${e.message}`, 'error') }
  }
  const onFile = (e) => {
    const f = e.target.files?.[0]; if (!f) return
    if (!/\.json$/i.test(f.name) || f.size > 200_000) return toast('Choose a .json file under 200 KB', 'error')
    f.text().then(load); e.target.value = ''
  }
  const sample = async () => { try { load(JSON.stringify(await api.sampleDisruption())) } catch (e) { toast(e.message, 'error') } }
  const preview = async () => {
    setBusy(true); setRes(null); setApplied(false)
    try { setRes(await api.previewDisruption(changes, +limit)); hist.reload() } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  const apply = async () => {
    setBusy(true)
    try { await api.applyDisruption(res.id); setApplied(true); toast('Change applied. Everyone has been notified.', 'ok'); hist.reload() } catch (e) { toast(e.message, 'error') } finally { setBusy(false); setConfirm(false) }
  }
  const stage = !res ? -1 : !res.feasible ? 0 : applied ? 4 : res.validation?.accepted ? 2 : 1
  const movedSet = new Set((res?.moved || []).map((m) => m.session_id))
  return (
    <>
      <PageHeader title="Disruption Management" subtitle="Load a change file, preview the minimum-movement repair, check the official validation, then approve. Nothing is applied automatically." />
      <ol className="mb-5 flex flex-wrap gap-2" aria-label="Workflow">{FLOW.map((s, i) => <li key={s}><Pill tone={i <= stage ? 'ok' : 'neutral'}>{i + 1}. {s}</Pill></li>)}</ol>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-lg font-extrabold text-navy">1. Change file</h2>
          <div className="flex flex-wrap gap-2"><input ref={file} type="file" accept=".json,application/json" className="sr-only" onChange={onFile} aria-label="Upload change file" />
            <Btn onClick={() => file.current.click()}><FileUp className="h-4 w-4" />Upload .json</Btn><Btn onClick={sample}>Load official sample</Btn></div>
          <label htmlFor="dj" className="label mt-4">Or paste JSON</label>
          <textarea id="dj" rows={7} className="field font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} placeholder='{"changes":[{"type":"faculty_unavailable","faculty_id":"F07","days":["MON"],"periods":[1,2,3,4,5,6,7,8,9]}]}' />
          <Btn className="mt-2" onClick={() => load(text)} disabled={!text.trim()}>Check file</Btn>
          {changes && <ul className="mt-4 grid gap-1.5">{changes.map((c, i) => <li key={i} className="clay-inset px-3 py-2 text-sm text-ink"><Pill tone="lav" className="mr-2">{titleCase(c.type)}</Pill>{describe(c)}</li>)}</ul>}
          <div className="mt-4 flex flex-wrap items-end gap-3"><div><label htmlFor="lm" className="label">Time limit (s)</label><input id="lm" type="number" min="10" max="270" className="field w-28" value={limit} onChange={(e) => setLimit(e.target.value)} /></div>
            <Btn variant="primary" onClick={preview} loading={busy && !res} disabled={!changes}><Play className="h-4 w-4" />Preview repair</Btn></div>
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-extrabold text-navy">2. Result</h2>
          {!res ? <Empty title="No preview yet" hint="Load a change file and press Preview. The current timetable is not touched until you approve." /> : !res.feasible ? (
            <div role="alert" className="grid gap-3"><Pill tone="bad">No valid repair exists</Pill><p className="text-sm text-ink">{res.conflict?.reason || 'The change conflicts with the hard constraints.'}</p>
              <pre className="clay-inset max-h-64 overflow-auto p-3 text-xs">{JSON.stringify(res.conflict, null, 2)}</pre></div>
          ) : (
            <div className="grid gap-4">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{[['Moved', res.summary.moved], ['Unchanged', res.summary.unchanged], ['Added', res.summary.added], ['Removed', res.summary.removed]].map(([k, v]) => <div key={k} className="clay-inset px-3 py-2 text-center"><p className="text-xs font-bold uppercase text-muted">{k}</p><p className="text-2xl font-extrabold text-navy">{v}</p></div>)}</div>
              <p className="text-sm text-ink">{res.minimality}</p>
              <div className="flex flex-wrap items-center gap-2"><Pill tone={res.validation.accepted ? 'ok' : 'bad'}><ShieldCheck className="h-3.5 w-3.5" />Official validator: {res.validation.accepted ? 'accepted' : 'NOT accepted'}</Pill>
                <Pill>{res.validation.hard_violation_count} hard violations</Pill><Pill>soft {res.soft_before} &rarr; {res.soft_after}</Pill><Pill tone={statusTone(res.status)}>{titleCase(res.status)}</Pill></div>
              {res.validation.stability && <p className="text-xs text-muted">Validator stability: {res.validation.stability.sessions_moved} moved ({res.validation.stability.time_changed} time, {res.validation.stability.room_only_changed} room-only).</p>}
              <Btn variant="mint" disabled={!res.validation.accepted || applied} onClick={() => setConfirm(true)}><Stamp className="h-4 w-4" />{applied ? 'Applied' : 'Admin approve and apply'}</Btn>
              {!res.validation.accepted && <p className="text-sm font-bold text-bad">This proposal failed official validation and cannot be applied.</p>}
            </div>)}
        </Card>
      </div>

      {res?.feasible && (
        <div className="mt-5 grid gap-5">
          <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Before &rarr; after (moved sessions)</h2>
            {res.moved.length === 0 ? <Empty title="No existing session had to move" /> : (
              <div className="grid gap-3">{res.moved.map((m) => (
                <div key={m.session_id} className="clay-sm grid items-center gap-3 p-3 sm:grid-cols-[1fr_auto_auto_auto_1.4fr]">
                  <span className="font-extrabold text-navy">{m.session_id}</span><Slot s={m.from} tone="bg-surface" /><ArrowRight className="hidden h-4 w-4 text-muted sm:block" /><Slot s={m.to} tone="bg-warn/30 ring-2 ring-warn/60" />
                  <span className="text-xs text-muted"><Pill tone={m.time_changed ? 'warn' : 'info'} className="mb-1">{m.time_changed ? 'Time changed' : 'Room only'}</Pill><br />{m.reason}</span></div>))}</div>)}
          </Card>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Added, removed, unchanged</h2>
              {res.added.map((a) => <p key={a.session_id} className="mb-1.5 text-sm"><Pill tone="ok">Added</Pill> <b className="text-navy">{a.session_id}</b> &rarr; {a.placed.day} P{a.placed.start_period} {a.placed.room_id}</p>)}
              {res.removed.map((r) => <p key={r} className="mb-1.5 text-sm"><Pill tone="bad">Removed</Pill> <b className="text-navy">{r}</b></p>)}
              <p className="mt-2 text-sm text-muted">{res.summary.unchanged} session(s) are untouched and stay in their original slot.</p></Card>
            <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Knock-on effects</h2>
              <p className="text-sm text-ink">Directly affected sessions: {Object.keys(res.affected || {}).length}</p>
              {res.exam_room_changes?.length > 0 && <p className="mt-2 text-sm text-ink">Exam rooms changed (slots unchanged): {res.exam_room_changes.map((x) => x.exam_id).filter(Boolean).join(', ') || 'see report'}</p>}
              <p className="mt-2 text-sm text-ink">Booking decisions changed: {res.booking_changes?.length || 0}</p>
              {res.booking_changes?.map((b) => <p key={b.request_id} className="text-xs text-muted">{b.request_id}: {b.before} &rarr; {b.after}</p>)}</Card>
          </div>
        </div>)}

      <Card className="mt-5"><h2 className="mb-3 text-lg font-extrabold text-navy">History</h2>
        {!hist.data?.disruptions?.length ? <Empty title="No disruptions yet" /> : <Table head={['ID', 'Status', 'Requested by', 'Moved', 'Created']}>{hist.data.disruptions.map((d) => <tr key={d.id}><td className="td font-bold text-navy">{d.id}</td><td className="td"><Pill tone={statusTone(d.status)}>{titleCase(d.status)}</Pill></td><td className="td">{d.requested_by}</td><td className="td">{d.moved ?? '-'}</td><td className="td">{new Date(d.created_at).toLocaleString()}</td></tr>)}</Table>}</Card>
      <Modal open={confirm} onClose={() => setConfirm(false)} title="Apply this change?" footer={<><Btn onClick={() => setConfirm(false)}>Not yet</Btn><Btn variant="primary" loading={busy} onClick={apply}>Approve and apply</Btn></>}>
        <p>This replaces the live timetable. {res?.summary?.moved} session(s) move; the official validator has accepted the result. Everyone is notified.</p></Modal>
    </>
  )
}
