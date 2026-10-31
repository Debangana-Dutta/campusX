import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageCircle, Minus, Send, X } from 'lucide-react'
import { api } from '../services/api'
import { useAuth } from '../contexts/AppContexts'

const QUICK = {
  student: [['When is my midsem?'], ['Show my timetable today'], ['Where is my next class?'], ['Do I have a free period today?'], ['Exam kab hai?']],
  faculty: [['Request a schedule change', '/app/assistant'], ['Mark myself unavailable', '/app/availability'], ['Find an alternative slot', '/app/assistant'], ['Explain my timetable']],
  club_representative: [['Book a venue', '/app/request-venue'], ['Check room availability', '/app/venues'], ['Track my booking', '/app/bookings'], ['Find an alternative venue', '/app/request-venue']],
  department_coordinator: [['Book a room', '/app/request-venue'], ['Requests to review', '/app/bookings']],
  admin: [['What changed in my timetable?'], ['Requests to review', '/app/bookings']],
}
const GREETING = "Hello! I'm Campus Buddy. Need help finding something?"

/** Optional floating helper (bottom-right). The rest of the app never depends on it. */
export default function BuddyWidget() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [nudge, setNudge] = useState(() => { try { return !sessionStorage.getItem('cx-buddy-seen') } catch { return true } })
  const [msgs, setMsgs] = useState([{ role: 'bot', text: GREETING }])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)
  const input = useRef(null)
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [msgs, open])
  useEffect(() => { if (open) input.current?.focus() }, [open])
  useEffect(() => { if (!nudge) return; const t = setTimeout(() => setNudge(false), 9000); return () => clearTimeout(t) }, [nudge])
  const toggle = (v) => { setOpen(v); setNudge(false); try { sessionStorage.setItem('cx-buddy-seen', '1') } catch { /* ignore */ } }

  const send = async (e, preset) => {
    e?.preventDefault?.()
    const t = (preset ?? q).trim(); if (!t || busy) return
    setMsgs((m) => [...m, { role: 'me', text: t }]); setQ(''); setBusy(true)
    try {
      const r = await api.ask(t)
      setMsgs((m) => [...m, { role: 'bot', text: r.answer }])
    } catch (x) {
      setMsgs((m) => [...m, { role: 'bot', error: true, text: x.status === 0 ? "I can't reach the server right now. You can still use every page; try me again in a moment." : `Sorry, I couldn't answer that. ${x.message}` }])
    } finally { setBusy(false) }
  }
  if (!user) return null
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-40 flex max-w-[calc(100vw-2rem)] flex-col items-end gap-3 sm:bottom-6 sm:right-6">
      {open && (
        <section role="dialog" aria-label="Campus Buddy chat" onKeyDown={(e) => e.key === 'Escape' && toggle(false)}
          className="glass pointer-events-auto flex h-[min(480px,calc(100vh-7.5rem))] w-[min(360px,calc(100vw-2rem))] flex-col overflow-hidden !rounded-2xl">
          <header className="flex items-center justify-between border-b border-[rgb(var(--peri)/.3)] px-4 py-3">
            <p className="font-bold text-navy">Campus Buddy</p>
            <div className="flex gap-1">
              <button className="btn btn-ghost !min-h-0 !p-2" onClick={() => toggle(false)} aria-label="Minimise chat"><Minus className="h-4 w-4" /></button>
              <button className="btn btn-ghost !min-h-0 !p-2" onClick={() => { setMsgs([{ role: 'bot', text: GREETING }]); toggle(false) }} aria-label="Close chat and clear it"><X className="h-4 w-4" /></button>
            </div>
          </header>
          <div className="flex-1 space-y-2.5 overflow-y-auto p-3" role="log" aria-live="polite">
            {msgs.map((m, i) => (
              <p key={i} className={`max-w-[88%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm ${m.role === 'me' ? 'ml-auto bg-lavender/60 font-medium text-navy' : m.error ? 'tone-bad' : 'clay-inset text-ink'}`}>{m.text}</p>))}
            {busy && <p className="text-xs text-muted" role="status">Looking that up…</p>}<div ref={end} />
          </div>
          <div className="flex flex-wrap gap-1.5 border-t border-[rgb(var(--peri)/.3)] px-3 pt-2" aria-label="Quick prompts">
            {(QUICK[user.role] || []).map(([label, to]) => to
              ? <Link key={label} to={to} onClick={() => toggle(false)} className="pill tone-lav hover:brightness-105">{label}</Link>
              : <button key={label} type="button" onClick={() => send(null, label)} disabled={busy} className="pill tone-lav hover:brightness-105">{label}</button>)}
          </div>
          <form onSubmit={send} className="flex gap-2 p-3 border-[rgb(var(--peri)/.3)] p-3"><label htmlFor="buddy-q" className="sr-only">Ask Campus Buddy</label>
            <input id="buddy-q" ref={input} className="field !min-h-[40px] !py-2" placeholder="Ask about your classes, rooms, exams…" value={q} onChange={(e) => setQ(e.target.value)} maxLength={400} />
            <button type="submit" className="btn btn-primary !min-h-[40px] !px-3" disabled={busy} aria-label="Send"><Send className="h-4 w-4" /></button></form>
        </section>)}
      {!open && nudge && <p role="status" className="clay-sm pointer-events-auto max-w-[240px] px-4 py-2.5 text-sm font-medium text-navy">{GREETING}</p>}
      <button onClick={() => toggle(!open)} aria-label={open ? 'Minimise Campus Buddy' : 'Open Campus Buddy'} aria-expanded={open}
        className="clay pointer-events-auto grid h-12 w-12 place-items-center !rounded-full text-accent transition hover:-translate-y-0.5"><MessageCircle className="h-6 w-6" /></button>
    </div>
  )
}
