import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Info, TriangleAlert, X } from 'lucide-react'
import { api, tokenStore } from '../services/api'

// ---------------------------------------------------------------- theme
const ThemeCtx = createContext(null)
export function ThemeProvider({ children }) {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try { localStorage.setItem('cx-theme', dark ? 'dark' : 'light') } catch { /* private mode */ }
  }, [dark])
  const value = useMemo(() => ({ dark, toggle: () => setDark((d) => !d) }), [dark])
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}
export const useTheme = () => useContext(ThemeCtx)

// ---------------------------------------------------------------- toasts
const ToastCtx = createContext(null)
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((message, kind = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setItems((l) => [...l, { id, message, kind }])
    setTimeout(() => setItems((l) => l.filter((x) => x.id !== id)), 5200)
  }, [])
  const icons = { ok: CheckCircle2, error: TriangleAlert, info: Info }
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-3" role="status" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => {
            const I = icons[t.kind] || Info
            const tone = t.kind === 'ok' ? 'text-ok' : t.kind === 'error' ? 'text-bad' : 'text-accent'
            return (
              <motion.div key={t.id} initial={{ opacity: 0, y: 16, scale: .96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, x: 40 }}
                className="clay pointer-events-auto flex items-start gap-3 p-4">
                <I className={`mt-0.5 h-5 w-5 shrink-0 ${tone}`} />
                <p className="flex-1 text-sm font-semibold text-navy">{t.message}</p>
                <button aria-label="Dismiss" onClick={() => setItems((l) => l.filter((x) => x.id !== t.id))}><X className="h-4 w-4 text-muted" /></button>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)

// ---------------------------------------------------------------- auth
const AuthCtx = createContext(null)
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!tokenStore.get())
  const [expired, setExpired] = useState(false)

  const logout = useCallback(() => { tokenStore.clear(); setUser(null) }, [])
  useEffect(() => {
    if (!tokenStore.get()) return
    api.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false))
  }, [])
  useEffect(() => {
    const h = () => { if (tokenStore.get()) { tokenStore.clear(); setUser(null); setExpired(true) } }
    window.addEventListener('cx-unauthorized', h)
    return () => window.removeEventListener('cx-unauthorized', h)
  }, [])
  const login = useCallback(async (username, password) => {
    const r = await api.login(username, password)
    tokenStore.set(r.token)
    setExpired(false)
    setUser(await api.me())
    return r
  }, [])
  const value = useMemo(() => ({ user, loading, login, logout, expired }), [user, loading, login, logout, expired])
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}
export const useAuth = () => useContext(AuthCtx)
