import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Inbox, Loader2, RefreshCw, X } from 'lucide-react'

export const Card = ({ className = '', children, as: T = 'section', ...p }) => <T className={`clay p-5 ${className}`} {...p}>{children}</T>

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="h-page">{title}</h1>{subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}</div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function Btn({ variant = '', loading, children, className = '', ...p }) {
  const v = { primary: 'btn-primary', mint: 'btn-mint', peach: 'btn-peach', ghost: 'btn-ghost' }[variant] || ''
  return <button className={`btn ${v} ${className}`} disabled={loading || p.disabled} {...p}>{loading && <Loader2 className="h-4 w-4 animate-spin" />}{children}</button>
}

export function Field({ label, id, hint, children }) {
  return <div><label htmlFor={id} className="label">{label}</label>{children}{hint && <p className="mt-1 text-xs text-muted">{hint}</p>}</div>
}

const TONES = { ok: 'tone-ok', warn: 'tone-warn', bad: 'tone-bad', info: 'tone-info', lav: 'tone-lav', neutral: 'tone-neutral' }
export const Pill = ({ tone = 'neutral', children, className = '' }) => <span className={`pill ${TONES[tone]} ${className}`}>{children}</span>

export const statusTone = (s) => ({ approved: 'ok', confirmed: 'ok', validated: 'info', accepted: 'ok', draft: 'warn', invalid: 'bad', rejected: 'bad',
  cancelled: 'neutral', proposed: 'warn', alternative_offered: 'lav', previewed: 'info', applied: 'ok', infeasible: 'bad' }[s] || 'neutral')

export function Stat({ label, value, hint, icon: Icon, tone = 'lavender' }) {
  return (
    <Card className="flex items-center gap-4">
      {Icon && <div className={`grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-${tone}/70 text-navy shadow-[inset_2px_2px_5px_rgba(255,255,255,.6),inset_-3px_-3px_6px_rgba(0,0,0,.08)]`}><Icon className="h-6 w-6" /></div>}
      <div className="min-w-0"><p className="text-xs font-bold uppercase tracking-wide text-muted">{label}</p>
        <p className="truncate text-2xl font-extrabold text-navy">{value ?? '-'}</p>{hint && <p className="truncate text-xs text-muted">{hint}</p>}</div>
    </Card>
  )
}

export const Skeleton = ({ className = 'h-24' }) => <div className={`skeleton ${className}`} aria-hidden />
export function LoadingBlock({ rows = 3 }) {
  return <div className="grid gap-4" role="status" aria-label="Loading"><span className="sr-only">Loading</span>{Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-24" />)}</div>
}
export function Empty({ title = 'Nothing here yet', hint, icon: I = Inbox, action }) {
  return (
    <div className="clay-inset flex flex-col items-center gap-2 px-6 py-12 text-center">
      <I className="h-10 w-10 text-muted" /><p className="text-lg font-bold text-navy">{title}</p>
      {hint && <p className="max-w-md text-sm text-muted">{hint}</p>}{action}
    </div>
  )
}
export function ErrorState({ error, onRetry }) {
  return (
    <div className="clay flex flex-col items-center gap-3 px-6 py-10 text-center" role="alert">
      <AlertTriangle className="h-10 w-10 text-danger" />
      <p className="text-lg font-bold text-navy">Something went wrong</p>
      <p className="max-w-lg text-sm text-muted">{error?.message || 'Unexpected error'}</p>
      {onRetry && <Btn onClick={onRetry}><RefreshCw className="h-4 w-4" />Try again</Btn>}
    </div>
  )
}
/** Renders loading/error/empty around data so every page handles all states the same way. */
export function Async({ state, children, rows, emptyIf, empty }) {
  if (state.loading && !state.data) return <LoadingBlock rows={rows} />
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />
  if (emptyIf && emptyIf(state.data)) return empty || <Empty />
  return children(state.data)
}

export function Modal({ open, onClose, title, children, footer }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const h = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', h); ref.current?.focus()
    return () => document.removeEventListener('keydown', h)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center bg-navy/30 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}
            initial={{ y: 24, scale: .96 }} animate={{ y: 0, scale: 1 }} exit={{ y: 24, scale: .96 }} className="clay max-h-[88vh] w-full max-w-lg overflow-auto p-6 outline-none">
            <div className="mb-4 flex items-start justify-between gap-3"><h2 className="text-xl font-extrabold text-navy">{title}</h2>
              <button onClick={onClose} aria-label="Close" className="btn btn-ghost !min-h-0 !p-2"><X className="h-5 w-5" /></button></div>
            <div className="text-sm text-ink">{children}</div>
            {footer && <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div role="tablist" className="clay-inset inline-flex flex-wrap gap-1 p-1.5">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={`rounded-xl px-3.5 py-2 text-sm font-bold transition ${value === t.id ? 'clay-sm text-navy' : 'text-muted hover:text-navy'}`}>{t.label}</button>
      ))}
    </div>
  )
}

export function Table({ head, children, className = '' }) {
  return (
    <div className={`clay-inset overflow-x-auto ${className}`}>
      <table className="w-full min-w-[560px] border-collapse">
        <thead><tr>{head.map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-[rgb(var(--peri)/.25)]">{children}</tbody>
      </table>
    </div>
  )
}
export const Toggle = ({ checked, onChange, label }) => (
  <label className="flex cursor-pointer items-center gap-3 text-sm font-bold text-navy">
    <input type="checkbox" className="peer sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    <span className="clay-inset relative h-7 w-12 rounded-full p-0.5 transition peer-checked:tone-ok peer-focus-visible:ring-2 peer-focus-visible:ring-accent">
      <span className={`clay-sm block h-6 w-6 rounded-full transition-transform ${checked ? 'translate-x-5' : ''}`} /></span>{label}
  </label>
)
