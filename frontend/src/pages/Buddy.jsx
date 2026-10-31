import { useEffect, useRef, useState } from 'react'
import { Bot, Send, Sparkles, UserRound } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../contexts/AppContexts'
import { Btn, Card, Field, PageHeader, Pill } from '../components/ui'

const SUGG = ['What are my classes today?', 'Where is my next lecture?', 'Do I have a free period tomorrow?', 'When is my next exam?', 'What changed in my timetable?', 'Aaj meri next class kaha hai?', 'Kal mera exam kab hai?']

export default function Buddy() {
  const { user } = useAuth()
  const ai = useApi(api.aiStatus, [])
  const needsScope = ['admin', 'department_coordinator'].includes(user.role)
  const ds = useApi(api.datasetSummary, [], { enabled: needsScope })
  const [group, setGroup] = useState('')
  const [msgs, setMsgs] = useState([{ role: 'bot', text: `Hi ${user.name.split(' ')[0]}! Ask me about your classes, rooms, free periods, exams or timetable changes, in English or Hinglish.` }])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [msgs])
  const ask = async (text) => {
    const t = (text ?? q).trim(); if (!t || busy) return
    setMsgs((m) => [...m, { role: 'me', text: t }]); setQ(''); setBusy(true)
    try { const r = await api.ask(t, group ? { group_id: group } : {}); setMsgs((m) => [...m, { role: 'bot', text: r.answer, meta: r }]) }
    catch (e) { setMsgs((m) => [...m, { role: 'bot', text: `I couldn't answer that: ${e.message}`, error: true }]) } finally { setBusy(false) }
  }
  return (
    <>
      <PageHeader title="Campus Buddy" subtitle="Answers come from your real timetable and exam data on the server. AI may only rephrase them; if it is unavailable you still get the same facts." />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="flex h-[68vh] min-h-[420px] flex-col lg:col-span-2 !p-4">
          <div className="flex-1 space-y-3 overflow-y-auto pr-1" role="log" aria-live="polite" aria-label="Conversation">
            {msgs.map((m, i) => (
              <div key={i} className={`flex gap-2.5 ${m.role === 'me' ? 'flex-row-reverse' : ''}`}>
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-2xl ${m.role === 'me' ? 'bg-peach/70' : 'bg-lavender/70'} text-navy`}>{m.role === 'me' ? <UserRound className="h-5 w-5" /> : <Bot className="h-5 w-5" />}</span>
                <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${m.role === 'me' ? 'bg-lavender/60 font-semibold text-navy' : m.error ? 'bg-rose/50 text-navy' : 'clay-inset text-ink'}`}>
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  {m.meta && <p className="mt-1.5"><Pill tone={m.meta.ai_used ? 'lav' : 'neutral'}>{m.meta.ai_used ? 'Phrased by Gemini' : 'Answered by rules'}</Pill>{m.meta.ai_error && !m.meta.ai_used && <span className="ml-2 text-[11px] text-muted">{m.meta.ai_error}</span>}</p>}
                </div>
              </div>))}
            {busy && <p className="text-sm text-muted" role="status">Looking that up&hellip;</p>}<div ref={end} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); ask() }} className="mt-3 flex gap-2"><label htmlFor="bq" className="sr-only">Your question</label>
            <input id="bq" className="field" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask in English or Hinglish..." maxLength={400} />
            <Btn type="submit" variant="primary" loading={busy} aria-label="Send"><Send className="h-4 w-4" /></Btn></form>
        </Card>
        <div className="grid h-fit gap-5">
          <Card><h2 className="mb-3 flex items-center gap-2 text-lg font-extrabold text-navy"><Sparkles className="h-5 w-5 text-accent" />Try asking</h2>
            <div className="flex flex-wrap gap-2">{SUGG.map((s) => <button key={s} onClick={() => ask(s)} className="pill bg-surface text-left text-navy hover:bg-lavender/40">{s}</button>)}</div></Card>
          {needsScope && <Card><Field label="Look up a student group" id="g" hint="Admins and coordinators can ask about any group."><select id="g" className="field" value={group} onChange={(e) => setGroup(e.target.value)}><option value="">None</option>{(ds.data?.groups || []).map((g) => <option key={g.id} value={g.id}>{g.id}</option>)}</select></Field></Card>}
          <Card><p className="text-sm text-muted">AI status: {ai.data ? (ai.data.gemini_configured ? 'Gemini is configured on the server.' : 'Gemini is not configured; the built-in lookup answers every question it supports.') : 'checking...'}</p></Card>
        </div>
      </div>
    </>
  )
}
