import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Circle, Download, Play, ShieldCheck, Stamp } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Field, PageHeader, Pill, Toggle, statusTone } from '../components/ui'
import { download, titleCase } from '../utils/format'

function Step({ n, title, done, children }) {
  return (
    <Card>
      <div className="mb-3 flex items-center gap-3"><span className={`grid h-9 w-9 place-items-center rounded-2xl font-extrabold text-navy ${done ? 'bg-mint/80' : 'bg-peri/60'}`}>{done ? <CheckCircle2 className="h-5 w-5" /> : n}</span>
        <h2 className="text-lg font-extrabold text-navy">{title}</h2></div>{children}
    </Card>
  )
}

export default function Generate() {
  const toast = useToast()
  const status = useApi(api.datasetStatus, [])
  const sum = useApi(api.summary, [])
  const [opt, setOpt] = useState({ seed: 42, time_limit_s: 120, include_exams: true, include_bookings: true, fresh: false })
  const [run, setRun] = useState({ busy: false, elapsed: 0, result: null, error: null })
  const timer = useRef(null)
  useEffect(() => () => clearInterval(timer.current), [])

  const start = async () => {
    setRun({ busy: true, elapsed: 0, result: null, error: null })
    const t0 = Date.now(); timer.current = setInterval(() => setRun((r) => ({ ...r, elapsed: Math.round((Date.now() - t0) / 1000) })), 1000)
    try { const r = await api.generate({ ...opt, seed: +opt.seed, time_limit_s: +opt.time_limit_s }); setRun({ busy: false, elapsed: Math.round((Date.now() - t0) / 1000), result: r, error: null }); toast(r.accepted ? 'Timetable generated and officially validated' : 'Generated, but the validator did not accept it', r.accepted ? 'ok' : 'error') }
    catch (e) { setRun({ busy: false, elapsed: Math.round((Date.now() - t0) / 1000), result: null, error: e }); toast(e.message, 'error') }
    finally { clearInterval(timer.current); sum.reload() }
  }
  const approve = async () => { try { await api.approve(); toast('Timetable approved', 'ok'); sum.reload() } catch (e) { toast(e.message, 'error') } }
  const exportIt = async () => { try { download('schedule.json', JSON.stringify(await api.exportSchedule(), null, 2)); toast('schedule.json exported', 'ok') } catch (e) { toast(e.message, 'error') } }
  const r = run.result
  const st = sum.data?.timetable_status

  return (
    <>
      <PageHeader title="Generate Timetable" subtitle="Runs the real OR-Tools solver on the backend, then the official validator. The request stays open until the solver finishes or reaches its time limit; no progress is simulated." />
      <div className="grid gap-5 xl:grid-cols-2">
        <Step n={1} title="Dataset readiness" done={status.data?.integrity?.ok}>
          <Async state={status} rows={1}>{(d) => (
            <div className="grid gap-2 text-sm">
              <p><Pill tone={d.integrity?.ok ? 'ok' : 'bad'}>{d.integrity?.ok ? 'Integrity checks passed' : 'Integrity errors'}</Pill></p>
              <dl className="grid grid-cols-2 gap-2">{Object.entries(d.integrity?.counts || {}).map(([k, v]) => <div key={k} className="clay-inset px-3 py-2"><dt className="text-xs font-bold uppercase text-muted">{titleCase(k)}</dt><dd className="text-lg font-extrabold text-navy">{v}</dd></div>)}</dl>
              <p className="text-muted">Teaching hours/week: <b className="text-navy">{d.integrity?.teaching_hours}</b>. {d.integrity?.warnings?.length || 0} data warning(s) noted (e.g. nonexistent requested rooms).</p>
            </div>)}</Async>
        </Step>
        <Step n={2} title="Options">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Random seed" id="seed" hint="Same seed + same data = same result."><input id="seed" type="number" className="field" value={opt.seed} onChange={(e) => setOpt({ ...opt, seed: e.target.value })} /></Field>
            <Field label="Time limit (seconds)" id="tl" hint="10-270. Longer can lower the soft penalty."><input id="tl" type="number" min="10" max="270" className="field" value={opt.time_limit_s} onChange={(e) => setOpt({ ...opt, time_limit_s: e.target.value })} /></Field>
          </div>
          <div className="mt-4 grid gap-3"><Toggle label="Schedule exams too" checked={opt.include_exams} onChange={(v) => setOpt({ ...opt, include_exams: v })} />
            <Toggle label="Decide Spectra bookings too" checked={opt.include_bookings} onChange={(v) => setOpt({ ...opt, include_bookings: v })} />
            <Toggle label="Cold start (ignore the saved timetable as a warm start)" checked={opt.fresh} onChange={(v) => setOpt({ ...opt, fresh: v })} /></div>
        </Step>
        <Step n={3} title="Run solver and validator" done={!!r}>
          <Btn variant="primary" onClick={start} loading={run.busy} className="w-full sm:w-auto"><Play className="h-4 w-4" />Generate with solver</Btn>
          {run.busy && <p className="mt-3 text-sm text-muted" role="status">Solver running on the server&hellip; {run.elapsed}s elapsed (limit {opt.time_limit_s}s). Please keep this tab open.</p>}
          {run.error && <div role="alert" className="clay-inset mt-3 p-4 text-sm"><p className="font-extrabold text-bad">Generation failed</p><p className="mt-1 text-ink">{run.error.message}</p>
            {run.error.detail && <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-muted">{JSON.stringify(run.error.detail, null, 2)}</pre>}</div>}
        </Step>
        <Step n={4} title="Results" done={r?.accepted}>
          {!r ? <p className="text-sm text-muted">Results appear here after a run. Current timetable: {st ? <Pill tone={statusTone(st)}>{titleCase(st)}</Pill> : 'none'}.</p> : (
            <div className="grid gap-3 text-sm">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {[['Solver status', r.status], ['Exam status', r.exam_status || '-'], ['Time', `${r.wall_time_s}s`], ['Sessions', `${sum.data?.sessions_scheduled ?? '-'} / ${sum.data?.sessions_total ?? '-'}`],
                  ['Hard violations', r.validation?.hard_violation_count], ['Soft penalty', r.validation?.soft_total]].map(([k, v]) => <div key={k} className="clay-inset px-3 py-2"><p className="text-xs font-bold uppercase text-muted">{k}</p><p className="text-lg font-extrabold text-navy">{String(v)}</p></div>)}
              </div>
              <p><Pill tone={r.accepted ? 'ok' : 'bad'}><ShieldCheck className="h-3.5 w-3.5" />Official validator: {r.accepted ? 'accepted' : 'NOT accepted'}</Pill></p>
              <p className="text-xs text-muted">Soft penalties {JSON.stringify(r.soft_penalties)}. Solver status is reported as CP-SAT returns it: only OPTIMAL means proven best; FEASIBLE means a valid schedule that may be improvable.</p>
            </div>)}
        </Step>
        <Step n={5} title="Approve and export" done={st === 'approved'}>
          <div className="flex flex-wrap gap-3">
            <Btn variant="mint" onClick={approve} disabled={st !== 'validated'}><Stamp className="h-4 w-4" />Approve timetable</Btn>
            <Btn onClick={exportIt} disabled={st !== 'approved' && st !== 'validated'}><Download className="h-4 w-4" />Export schedule.json</Btn>
          </div>
          <p className="mt-3 text-sm text-muted">{st === 'validated' ? 'Validated by the official validator. Approve it to publish.' : st === 'approved' ? 'Approved. Everyone sees it as the official timetable.' : st === 'invalid' ? 'This schedule is invalid and cannot be approved or exported.' : 'Generate a timetable first.'}</p>
        </Step>
      </div>
    </>
  )
}
