import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate, Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Bell, ChevronLeft, ChevronRight, LogOut, Menu, Moon, Search, Sun, X } from 'lucide-react'
import { useAuth, useTheme } from '../contexts/AppContexts'
import { Logo, LogoMark } from '../components/Logo'
import { NAV, ROLE_LABEL } from '../utils/nav'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { Pill } from '../components/ui'

function NavList({ items, collapsed, onNavigate }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1.5">
      {items.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} onClick={onNavigate} title={collapsed ? n.label : undefined}
          className={({ isActive }) => `flex min-h-[44px] items-center gap-3 rounded-2xl px-3.5 text-sm font-bold transition ${isActive ? 'clay-sm text-navy' : 'text-muted hover:bg-lavender/25 hover:text-navy'}`}>
          <n.icon className="h-5 w-5 shrink-0" />{!collapsed && <span className="truncate">{n.label}</span>}
        </NavLink>
      ))}
    </nav>
  )
}

function Bell_({ unread }) {
  return (
    <Link to="/app/notifications" aria-label={`Notifications, ${unread} unread`} className="btn !p-2.5 relative">
      <Bell className="h-5 w-5" />
      {unread > 0 && <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-bad px-1 text-[11px] font-extrabold text-white">{unread > 9 ? '9+' : unread}</span>}
    </Link>
  )
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const { dark, toggle } = useTheme()
  const nav = useNavigate()
  const loc = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [q, setQ] = useState('')
  const items = NAV[user.role] || []
  const notif = useApi(api.notifications, [])
  const reload = useRef(notif.reload); reload.current = notif.reload
  useEffect(() => { const t = setInterval(() => reload.current(), 30000); return () => clearInterval(t) }, [])
  useEffect(() => { setDrawer(false); reload.current() }, [loc.pathname])
  const current = items.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)))
  const crumbs = ['Campus X', current?.label || 'Overview']

  const search = (e) => {
    e.preventDefault()
    const hit = items.find((n) => n.label.toLowerCase().includes(q.trim().toLowerCase()))
    if (hit) { nav(hit.to); setQ('') }
  }
  const side = (compact, onNavigate) => (
    <div className="flex h-full flex-col gap-5">
      <div className={`flex items-center ${compact ? 'justify-center' : 'px-2'}`}>{compact ? <LogoMark size={38} /> : <Logo />}</div>
      <NavList items={items} collapsed={compact} onNavigate={onNavigate} />
    </div>
  )
  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[200] btn">Skip to content</a>
      <aside className={`clay sticky top-3 m-3 hidden h-[calc(100vh-1.5rem)] shrink-0 overflow-y-auto p-4 transition-[width] lg:block ${collapsed ? 'w-[84px]' : 'w-[270px]'}`}>{side(collapsed)}</aside>
      <AnimatePresence>
        {drawer && (
          <motion.div className="fixed inset-0 z-50 bg-navy/30 backdrop-blur-sm lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setDrawer(false)}>
            <motion.aside initial={{ x: -320 }} animate={{ x: 0 }} exit={{ x: -320 }} onClick={(e) => e.stopPropagation()} className="clay m-3 h-[calc(100vh-1.5rem)] w-[280px] overflow-y-auto p-4" aria-label="Navigation drawer">
              <button className="btn btn-ghost !min-h-0 float-right !p-2" onClick={() => setDrawer(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
              {side(false, () => setDrawer(false))}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="clay sticky top-3 z-30 m-3 mb-0 flex items-center gap-2 p-2.5 sm:gap-3 sm:p-3">
          <button className="btn !p-2.5 lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          <button className="btn !p-2.5 hidden lg:inline-flex" onClick={() => setCollapsed((c) => !c)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}</button>
          <div className="hidden min-w-0 md:block">
            <p className="truncate text-xs font-bold text-muted">{crumbs.join(' / ')}</p>
          </div>
          <form onSubmit={search} role="search" className="relative ml-auto hidden min-w-0 flex-1 max-w-xs sm:block">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input aria-label="Jump to page" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Jump to a page..." className="field !pl-10" list="pages" />
            <datalist id="pages">{items.map((n) => <option key={n.to} value={n.label} />)}</datalist>
          </form>
          <div className="ml-auto flex items-center gap-2 sm:ml-0">
            <Bell_ unread={notif.data?.unread || 0} />
            <button className="btn !p-2.5" onClick={toggle} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>{dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</button>
            <ProfileMenu user={user} onLogout={() => { logout(); nav('/') }} />
          </div>
        </header>
        <main id="main" className="min-w-0 flex-1 p-3 sm:p-5">
          <AnimatePresence mode="wait">
            <motion.div key={loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .22 }}><Outlet /></motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}

function ProfileMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div className="relative" ref={ref}>
      <button className="btn !px-3" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        <span className="grid h-7 w-7 place-items-center rounded-full bg-lavender/80 text-xs font-extrabold text-navy">{user.name?.[0] || '?'}</span>
        <span className="hidden max-w-[120px] truncate sm:inline">{user.name}</span>
      </button>
      {open && (
        <div role="menu" className="clay absolute right-0 top-14 z-40 w-64 p-4">
          <p className="truncate font-extrabold text-navy">{user.name}</p>
          <Pill tone="lav" className="mt-2">{ROLE_LABEL[user.role]}</Pill>
          {user.mode === 'local' && <p className="mt-3 text-xs text-muted">Signed in with LOCAL DEMO authentication (not production).</p>}
          <button role="menuitem" className="btn btn-peach mt-4 w-full" onClick={onLogout}><LogOut className="h-4 w-4" />Sign out</button>
        </div>
      )}
    </div>
  )
}
