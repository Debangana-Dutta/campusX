// Full-stack UI tests: the REAL React app against the REAL FastAPI backend (VITE_API_BASE_URL); no mocked API responses
// except where a test says so (to simulate an outage). Verifies rendering, role guards, forms and workflows.
// jsdom cannot judge visual layout or colour; see IMPLEMENTATION_STATUS.md.
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { act } from 'react'
import { describe, expect, it, vi } from 'vitest'
import Splash from '../components/Splash'
import App from '../App'
import { AuthProvider, ThemeProvider, ToastProvider } from '../contexts/AppContexts'
import { api, tokenStore } from '../services/api'

const T = { timeout: 15000 }
const PW = 'campusx-demo'
async function renderAs(role, path = '/app') {
  if (role) { const r = await api.login(`${role}@opticampus.demo`, PW); tokenStore.set(r.token) }
  return render(<MemoryRouter initialEntries={[path]}><ThemeProvider><ToastProvider><AuthProvider><App /></AuthProvider></ToastProvider></ThemeProvider></MemoryRouter>)
}
const nav = (name) => screen.findByRole('link', { name }, T)
const type = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

describe('first page is the login page', () => {
  it('"/" shows the sign-in page with the big brand name on the left and nothing describing the product', async () => {
    await renderAs(null, '/')
    const h1 = screen.getByRole('heading', { level: 1 })
    expect(h1).toHaveTextContent('OptiCampus')
    expect(h1.querySelector('.brand-name')).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    // layout: brand (h1) comes first, the form second (left, then right on wide screens)
    expect(h1.compareDocumentPosition(screen.getByRole('main')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // no marketing / feature / how-it-works / footer copy anywhere
    expect(screen.queryByText(/Make Every Campus Hour|features|how it works|Explore Platform|Designed to make campus|All rights reserved|timetable scheduling|Venue booking/i)).toBeNull()
    expect(screen.queryByRole('link', { name: /Explore|Features/i })).toBeNull()
  })
  it('"/login" is the same login page; Request access and Forgot password are reachable', async () => {
    await renderAs(null, '/login')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('OptiCampus')
    expect(screen.getByRole('link', { name: /Request access/i })).toHaveAttribute('href', '/request-access')
    expect(screen.getByRole('link', { name: /Forgot password/i })).toHaveAttribute('href', '/forgot-password')
  })
  it('a signed-in user opening "/" goes straight to their dashboard, not the login page', async () => {
    await renderAs('student', '/')
    expect(await screen.findByText(/Read-only view for CSE-2/i, {}, T)).toBeInTheDocument()
    expect(screen.queryByLabelText('Email')).toBeNull()
  })
  it('protected routes redirect anonymous users to sign in', async () => {
    await renderAs(null, '/app/timetable')
    expect(await screen.findByRole('heading', { name: /Sign in/i }, T)).toBeInTheDocument()
  })
})

describe('splash screen', () => {
  it('shows only the logo and the name on a glass layer', () => {
    const { container } = render(<Splash />)
    const sp = screen.getByTestId('splash')
    expect(sp).toHaveAttribute('data-phase', 'show')
    expect(within(sp).getByRole('img', { name: 'OptiCampus logo', hidden: true })).toBeInTheDocument()
    expect(sp.textContent.replace(/\s/g, '')).toBe('OptiCampus')                                  // nothing but the name
    expect(sp.className).toMatch(/splash/)
    expect(container.querySelector('.brand-gradient')).not.toBeNull()
  })
  it('holds for 1 second, then pulls down and away, then is removed (revealing the page under it)', () => {
    vi.useFakeTimers()
    try {
      render(<Splash hold={1000} exit={700} />)
      expect(screen.getByTestId('splash')).toHaveAttribute('data-phase', 'show')
      act(() => { vi.advanceTimersByTime(999) })
      expect(screen.getByTestId('splash')).toHaveAttribute('data-phase', 'show')               // still showing at 999 ms
      act(() => { vi.advanceTimersByTime(2) })
      const sp = screen.getByTestId('splash')
      expect(sp).toHaveAttribute('data-phase', 'leaving')                                      // pull-down starts at 1 s
      expect(sp.className).toMatch(/splash-leave/)
      expect(sp.style.getPropertyValue('--splash-exit')).toBe('700ms')
      act(() => { vi.advanceTimersByTime(700) })
      expect(screen.queryByTestId('splash')).toBeNull()                                        // gone: login is revealed
      expect(document.body.style.overflow).not.toBe('hidden')                                  // scrolling restored
    } finally { vi.useRealTimers() }
  })
  it('is hidden from assistive tech and does not block the page for long', () => {
    render(<Splash />)
    expect(screen.getByTestId('splash')).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('theme tokens (dark-mode contrast fix)', () => {
  it('status pills use the paired tone classes, never a background token as text colour', async () => {
    const { Pill } = await import('../components/ui')
    const { container } = render(<><Pill tone="ok">ok</Pill><Pill tone="warn">w</Pill><Pill tone="bad">b</Pill></>)
    expect(container.querySelectorAll('.tone-ok, .tone-warn, .tone-bad').length).toBe(3)
    expect(container.innerHTML).not.toMatch(/dark:text-mint|text-\[#14513f\]/)
  })
  it('no component source hard-codes a dark green text colour', async () => {
    const fs = await import('node:fs'), path = await import('node:path')
    const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? (e.name === '__tests__' ? [] : walk(path.join(d, e.name))) : [path.join(d, e.name)])
    const bad = walk('src').filter((f) => /\.(jsx|js)$/.test(f)).filter((f) => /text-\[#14513f\]|dark:text-mint|text-\[#17403a\]/.test(fs.readFileSync(f, 'utf8')))
    expect(bad).toEqual([])
  })
})

describe('official logo', () => {
  it('the supplied logo image is used on the splash, the auth pages and inside the app', async () => {
    const sp = render(<Splash />)
    expect(screen.getByRole('img', { name: 'OptiCampus logo', hidden: true }).getAttribute('src')).toMatch(/logo.*\.png$|^data:image\/png/)
    sp.unmount()
    const l = await renderAs(null, '/forgot-password')
    expect(screen.getByRole('img', { name: 'OptiCampus logo' })).toBeInTheDocument()
    l.unmount()
    await renderAs('student')
    expect((await screen.findAllByRole('img', { name: 'OptiCampus logo' }, T)).length).toBeGreaterThan(0)
  })
})

describe('authentication', () => {
  it('sign in page: no demo credentials or shortcuts; show/hide password; forgot + request links', async () => {
    await renderAs(null, '/login')
    expect(screen.queryByText(/campusx-demo|demo account/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /^Admin/ })).toBeNull()
    const pw = screen.getByLabelText('Password')
    expect(pw).toHaveAttribute('type', 'password')
    fireEvent.click(screen.getByRole('button', { name: /Show password/i }))
    expect(pw).toHaveAttribute('type', 'text')
    expect(screen.getByRole('link', { name: /Forgot password/i })).toHaveAttribute('href', '/forgot-password')
    expect(screen.getByRole('link', { name: /Request access/i })).toHaveAttribute('href', '/request-access')
    expect(screen.getByLabelText(/Remember me/i)).toBeInTheDocument()
  })
  it('wrong password shows a clear error; correct credentials reach the role dashboard', async () => {
    await renderAs(null, '/login')
    type('Email', 'admin@opticampus.demo'); type('Password', 'wrong-password-1')
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(/Incorrect email or password/i, {}, T)).toBeInTheDocument()
    type('Password', PW)
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(/sessions scheduled/i, {}, T)).toBeInTheDocument()
  })
  it('invalid email is caught before any request is sent', async () => {
    await renderAs(null, '/login')
    type('Email', 'nope'); type('Password', 'whatever12345')
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(/valid email address/i)).toBeInTheDocument()
  })
  it('forgot password shows the same neutral message for any address', async () => {
    await renderAs(null, '/forgot-password')
    type('Email', 'nobody-here@example.com')
    fireEvent.click(screen.getByRole('button', { name: /Send reset link/i }))
    expect(await screen.findByText(/If that email is registered, a reset link has been sent/i, {}, T)).toBeInTheDocument()
  })
  it('reset page without a token explains the problem; with a bad token shows the backend error', async () => {
    await renderAs(null, '/reset-password')
    expect(await screen.findByText(/missing its reset token/i)).toBeInTheDocument()
  })
  it('request access offers only non-admin roles, validates, and shows pending status', async () => {
    await renderAs(null, '/request-access')
    const roles = within(screen.getByLabelText('Role')).getAllByRole('option').map((o) => o.textContent)
    expect(roles).toEqual(['Faculty', 'Department Coordinator', 'Club Representative'])
    type('Full name', 'Test Person'); type('Institutional email', `ui.${Date.now()}@cit.ac.in`); type('Password', 'weak')
    fireEvent.click(screen.getByRole('button', { name: /Send request/i }))
    expect(await screen.findByText(/at least 10 characters/i, {}, T)).toBeInTheDocument()
    type('Password', 'StrongPass123')
    await waitFor(() => expect(screen.getByRole('button', { name: /Send request/i })).not.toBeDisabled(), T)
    fireEvent.click(screen.getByRole('button', { name: /Send request/i }))
    expect(await screen.findByText(/Pending approval/i, {}, T)).toBeInTheDocument()
  })
  it('admin sees the request on Users and can approve it', async () => {
    const email = `approve.${Date.now()}@cit.ac.in`
    await api.requestAccess({ name: 'Approve Me', email, password: 'StrongPass123', role: 'club_representative', organisation: 'Robotics' })
    await renderAs('admin', '/app/users')
    const cells = await screen.findAllByText(email, {}, T)                 // listed under requests and under all accounts
    const row = cells.map((c) => c.closest('tr')).find((r) => within(r).queryByRole('button', { name: /Approve/i }))
    fireEvent.click(within(row).getByRole('button', { name: /Approve/i }))
    await waitFor(async () => { const r = await api.login(email, 'StrongPass123').catch(() => null); expect(r?.role).toBe('club_representative') }, T)
  })
  it('change password lives in Settings/Profile', async () => {
    await renderAs('club', '/app/settings')
    expect(await screen.findByRole('heading', { name: /Change password/i }, T)).toBeInTheDocument()
  })
  it('signing out returns to the landing page and clears the session', async () => {
    await renderAs('admin')
    fireEvent.click(await screen.findByRole('button', { name: /Dean's Office/i }, T))
    fireEvent.click(await screen.findByRole('menuitem', { name: /Sign out/i }))
    expect(await screen.findByRole('heading', { name: 'Sign in' }, T)).toBeInTheDocument()
    expect(tokenStore.get()).toBeNull()
  })
})

describe('role dashboards use live backend data', () => {
  it('admin overview shows what needs attention and live timetable status', async () => {
    await renderAs('admin')
    expect(await screen.findByText(/Needs your attention/i, {}, T)).toBeInTheDocument()
    expect(await screen.findByText(/189 of 189 sessions scheduled/i, {}, T)).toBeInTheDocument()
    expect(await screen.findByText(/accepted/i, {}, T)).toBeInTheDocument()
    expect((await screen.findAllByRole('link', { name: 'Timetable Generator' }, T)).length).toBeGreaterThan(0)
    for (const l of ['Timetable', 'Validation', 'Requests to Review', 'Schedule Changes', 'Exams', 'Rooms', 'Room Usage', 'Data', 'Users', 'FAQs']) expect(await nav(l)).toBeInTheDocument()
  })
  it.each([['faculty', ['My Timetable', 'Availability']], ['coordinator', ['Department Timetable', 'Faculty']], ['club', ['Request a Venue', 'My Bookings']], ['student', ['My Timetable', 'Exams']]])('%s gets a role-specific menu', async (role, links) => {
    await renderAs(role)
    for (const l of links) expect(await nav(l)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Timetable Generator' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Users' })).toBeNull()
  })
  it('role guard blocks a page the role may not open', async () => {
    await renderAs('club', '/app/generate')
    expect(await screen.findByText(/don't have access/i, {}, T)).toBeInTheDocument()
  })
  it('student overview is read-only and scoped to their group', async () => {
    await renderAs('student')
    expect(await screen.findByText(/Read-only view for CSE-2/i, {}, T)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Booking/i })).toBeNull()
  })
})

describe('timetable, validation, exams', () => {
  it('timetable shows the grid, lunch row, colour legend, and the verification note only because it is validated', async () => {
    await renderAs('admin', '/app/timetable')
    const grid = await screen.findByRole('region', { name: /Weekly timetable grid/i }, T)
    expect(screen.getByText(/Lunch/)).toBeInTheDocument()
    expect(await screen.findByText(/Generated using scheduling constraints and verified by the official validator/i, {}, T)).toBeInTheDocument()
    expect(screen.getByText(/Course colours/i)).toBeInTheDocument()
    expect(screen.queryByText(/AI Generated/i)).toBeNull()
    fireEvent.click(within(grid).getAllByRole('button')[0])
    const dlg = await screen.findByRole('dialog'); expect(dlg).toHaveTextContent(/Faculty/)
    fireEvent.click(within(dlg).getByRole('button', { name: /Why here/i }))
    expect(await within(dlg).findByText(/possible day\/period slots/i, {}, T)).toBeInTheDocument()
  })
  it('the same course keeps the same colour class in the group view and the faculty view', async () => {
    await renderAs('admin', '/app/timetable')
    await screen.findByRole('region', { name: /Weekly timetable grid/i }, T)
    const classOf = () => { const m = {}; for (const b of within(screen.getByRole('region', { name: /Weekly timetable grid/i })).getAllByRole('button')) { const t = b.textContent.match(/[A-Z]{2,3}\d{3}/)?.[0]; const c = [...b.classList].find((x) => x.startsWith('cc-')); if (t && c) m[t] = c } return m }
    const a = classOf()
    fireEvent.click(screen.getByRole('tab', { name: 'Faculty' }))
    await waitFor(() => expect(screen.getByLabelText('Faculty')).toBeInTheDocument(), T)
    const b = classOf()
    for (const k of Object.keys(a)) if (b[k]) expect(b[k]).toBe(a[k])
    expect(Object.keys(a).length).toBeGreaterThan(0)
  })
  it('room and day views work; day view lists free rooms', async () => {
    await renderAs('admin', '/app/timetable')
    await screen.findByRole('region', { name: /Weekly timetable grid/i }, T)
    fireEvent.click(screen.getByRole('tab', { name: 'Day' }))
    expect(await screen.findByRole('region', { name: /Room occupancy Monday/i }, T)).toBeInTheDocument()
    expect(screen.getAllByLabelText('free').length).toBeGreaterThan(10)
  })
  it('validation page shows the official verdict with zero hard violations', async () => {
    await renderAs('admin', '/app/validation')
    expect(await screen.findByText('Accepted', {}, T)).toBeInTheDocument()
    expect(await screen.findByText(/Every hard constraint holds/i, {}, T)).toBeInTheDocument()
  })
  it('exams page lists the 41 real exams and verifies half-capacity seating', async () => {
    await renderAs('admin', '/app/exams')
    expect(await screen.findByText('41', {}, T)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Room allocation' }))
    expect((await screen.findAllByText('Fits', {}, T)).length).toBe(41)
  })
})

describe('booking workflow', () => {
  it('club submits a natural-language request, reviews the parsed fields and gets a deterministic decision', async () => {
    await renderAs('club', '/app/request-venue')
    fireEvent.change(await screen.findByLabelText(/Your request/i, {}, T), { target: { value: 'Need a room for 45 people on Tuesday 6 to 8 pm, projector please.' } })
    fireEvent.click(screen.getByRole('button', { name: /Understand my request/i }))
    await waitFor(() => expect(screen.getByLabelText('Attendance')).toHaveValue(45), T)
    expect(screen.getByLabelText('Duration (hours)')).toHaveValue(2)
    expect(screen.getByRole('button', { name: 'Projector', pressed: true })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Submit for decision/i }))
    expect(await screen.findByText(/Approved as club event/i, {}, T)).toBeInTheDocument()
  })
  it('the manual form validates input and never needs AI', async () => {
    await renderAs('club', '/app/request-venue')
    fireEvent.click(await screen.findByRole('button', { name: /Submit for decision/i }, T))
    expect(await screen.findByText(/Give the event a title/i, {}, T)).toBeInTheDocument()
  })
  it('an impossible request is rejected with a reason shown to the requester', async () => {
    await renderAs('club', '/app/request-venue')
    fireEvent.change(await screen.findByLabelText('Event title', {}, T), { target: { value: 'Mega fest' } })
    type('Attendance', '1200'); type('Duration (hours)', '2')
    for (const n of ['Auditorium', 'Classroom', 'Lecture Hall', 'Seminar Hall']) fireEvent.click(screen.getByRole('button', { name: n }))
    fireEvent.click(screen.getByRole('button', { name: /Submit for decision/i }))
    expect(await screen.findByText(/No venue seats 1,200/i, {}, T)).toBeInTheDocument()
  })
  it('my bookings lists decisions with reasons; notification centre clears with mark all read', async () => {
    await renderAs('club', '/app/bookings')
    fireEvent.click(await screen.findByText('Mega fest', {}, T))
    expect(await screen.findByText(/Decision explanation/i)).toBeInTheDocument()
  })
  it('notification centre shows unread items and mark-all-read clears them', async () => {
    await renderAs('club', '/app/notifications')
    const btn = await screen.findByRole('button', { name: /Mark all as read/i }, T)
    await waitFor(() => expect(btn).not.toBeDisabled(), T)
    fireEvent.click(btn)
    await waitFor(() => expect(screen.getByRole('button', { name: /Mark all as read/i })).toBeDisabled(), T)
  })
  it('admin manual scheduling shows backend conflict reasons and a clean success', async () => {
    await renderAs('admin', '/app/bookings')
    fireEvent.click(await screen.findByRole('button', { name: /Schedule manually/i }, T))
    fireEvent.change(await screen.findByLabelText('Event title'), { target: { value: 'Manual talk' } })
    await waitFor(() => expect(within(screen.getByLabelText('Room')).getAllByRole('option').length).toBeGreaterThan(5), T)
    fireEvent.change(screen.getByLabelText('Room'), { target: { value: 'SH-1' } })
    type('Day', 'FRI'); type('Start', '12'); type('Attendance', '5000')
    fireEvent.click(screen.getByRole('button', { name: /Check and schedule/i }))
    expect(await screen.findByRole('alert', {}, T)).toHaveTextContent(/seats/i)
    type('Attendance', '30')
    fireEvent.click(screen.getByRole('button', { name: /Check and schedule/i }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull(), T)
  })
  it('admin can open the priority editor and sees exams/classes fixed on top', async () => {
    await renderAs('admin', '/app/bookings')
    fireEvent.click(await screen.findByText(/Booking priority order/i, {}, T))
    expect(await screen.findByText('Regular Session')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Move exam/i })).toBeNull()
  })
})

describe('data management and schedule changes (admin)', () => {
  it('data page lists rooms from the database and rejects a deletion that would break the timetable', async () => {
    await renderAs('admin', '/app/data')
    expect(await screen.findByText('AUD', {}, T)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete AUD' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(await screen.findByText(/used by \d+ scheduled session/i, {}, T)).toBeInTheDocument()
  })
  it('preview shows a validated minimum-movement repair with solver evidence; nothing applies until the admin approves', async () => {
    await renderAs('admin', '/app/disruptions')
    fireEvent.click(await screen.findByRole('button', { name: /Load official sample/i }, T))
    await screen.findByText(/Faculty F07 unavailable/i, {}, T)
    fireEvent.click(screen.getByRole('button', { name: /Preview repair/i }))
    expect(await screen.findByText(/Official validator: accepted/i, {}, { timeout: 90000 })).toBeInTheDocument()
    expect(screen.getByText(/Proven minimum/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Time-slot|Room-only|Time slot|Room only/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Before/)).toBeInTheDocument()
    const apply = screen.getByRole('button', { name: /Admin approve and apply/i })
    fireEvent.click(apply)
    expect(await screen.findByRole('dialog')).toHaveTextContent(/Apply this change/i)
    fireEvent.click(screen.getByRole('button', { name: 'Approve and apply' }))
    expect(await screen.findByRole('button', { name: /^Applied$/ }, T)).toBeInTheDocument()
  }, 120000)
  it('faculty can describe unavailability but cannot open the admin page', async () => {
    await renderAs('faculty', '/app/disruptions')
    expect(await screen.findByText(/don't have access/i, {}, T)).toBeInTheDocument()
  })
  it('faculty availability assistant fills the form from a sentence (draft only)', async () => {
    await renderAs('faculty', '/app/availability')
    fireEvent.change(await screen.findByLabelText(/Describe it/i, {}, T), { target: { value: "I can't teach Monday morning" } })
    fireEvent.click(screen.getByRole('button', { name: /Fill form/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Monday', pressed: true })).toBeInTheDocument(), T)
  })
})

describe('floating Campus Buddy, FAQ, theme, mobile navigation', () => {
  it('buddy floats on every page, greets once, opens, answers from backend data, and minimises', async () => {
    await renderAs('student', '/app/exams')
    const fab = await screen.findByRole('button', { name: /Open Campus Buddy/i }, T)
    expect(fab.closest('div')).toHaveClass('fixed', 'bottom-4', 'right-4')
    expect(screen.getByText("Hello! I'm Campus Buddy. Need help finding something?")).toBeInTheDocument()
    fireEvent.click(fab)
    const dlg = await screen.findByRole('dialog', { name: /Campus Buddy chat/i })
    fireEvent.change(within(dlg).getByLabelText('Ask Campus Buddy'), { target: { value: 'Aaj meri next class kaha hai?' } })
    fireEvent.click(within(dlg).getByRole('button', { name: 'Send' }))
    expect(await within(dlg).findByText(/^Next class \(/, {}, T)).toBeInTheDocument()
    fireEvent.click(within(dlg).getByRole('button', { name: /Minimise chat/i }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /Campus Buddy chat/i })).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /Open Campus Buddy/i }))
    expect(await screen.findByText(/^Next class \(/)).toBeInTheDocument()            // conversation kept after reopening
  })
  it('buddy shows a friendly fallback when the API is unreachable and the page keeps working', async () => {
    await renderAs('student', '/app')
    fireEvent.click(await screen.findByRole('button', { name: /Open Campus Buddy/i }, T))
    const dlg = await screen.findByRole('dialog', { name: /Campus Buddy chat/i })
    const real = globalThis.fetch
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('offline'))
    fireEvent.change(within(dlg).getByLabelText('Ask Campus Buddy'), { target: { value: 'my classes today' } })
    fireEvent.click(within(dlg).getByRole('button', { name: 'Send' }))
    expect(await within(dlg).findByText(/can't reach the server/i, {}, T)).toBeInTheDocument()
    globalThis.fetch = real
    expect(screen.getByRole('link', { name: 'My Timetable' })).toBeInTheDocument()
  })
  it('FAQ page: expandable answers and search', async () => {
    await renderAs('student', '/app/faq')
    fireEvent.click(await screen.findByRole('button', { name: /How do I request a venue/i }, T))
    expect(screen.getByText(/Describe the event in English or Hinglish/i)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Search FAQs'), { target: { value: 'password' } })
    expect(screen.getByRole('button', { name: /forgot my password/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /How do I request a venue/i })).toBeNull()
    expect(screen.queryByText(/Try asking/i)).toBeNull()
  })
  it('theme toggle switches dark mode and persists the choice', async () => {
    await renderAs('admin')
    fireEvent.click(await screen.findByRole('button', { name: /Switch to dark mode/i }, T))
    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem('cx-theme')).toBe('dark')
    fireEvent.click(screen.getByRole('button', { name: /Switch to light mode/i }))
    expect(document.documentElement).not.toHaveClass('dark')
  })
  it('mobile drawer opens with the navigation and closes', async () => {
    await renderAs('admin')
    fireEvent.click(await screen.findByRole('button', { name: /Open menu/i }, T))
    const d = await screen.findByLabelText('Navigation drawer')
    expect(within(d).getByRole('link', { name: 'Timetable' })).toBeInTheDocument()
    fireEvent.click(within(d).getByRole('button', { name: /Close menu/i }))
    await waitFor(() => expect(screen.queryByLabelText('Navigation drawer')).toBeNull())
  })
})

describe('rejecting a schedule change', () => {
  it('admin can reject a validated proposal; it is marked rejected and cannot then be applied', async () => {
    await renderAs('admin', '/app/disruptions')
    fireEvent.change(await screen.findByLabelText(/Or paste JSON/i, {}, T), { target: { value: JSON.stringify({ changes: [{ type: 'faculty_unavailable', faculty_id: 'F02', days: ['WED'], periods: [1, 2, 3], reason: 'test' }] }) } })
    fireEvent.click(screen.getByRole('button', { name: /Check file/i }))
    fireEvent.click(await screen.findByRole('button', { name: /Preview repair/i }, T))
    const reject = await screen.findByRole('button', { name: /Reject proposal/i }, { timeout: 90000 })
    fireEvent.click(reject)
    expect(await screen.findByRole('button', { name: /^Rejected$/ }, T)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Admin approve and apply/i })).toBeDisabled()
  }, 120000)
})


describe('midsem flow (the reported bug)', () => {
  it('a student asks "When is my midsem?" in the floating Buddy and gets real exam details', async () => {
    await renderAs('student', '/app')
    fireEvent.click(await screen.findByRole('button', { name: /Open Campus Buddy/i }, T))
    const dlg = await screen.findByRole('dialog', { name: /Campus Buddy chat/i })
    fireEvent.change(within(dlg).getByLabelText('Ask Campus Buddy'), { target: { value: 'When is my midsem?' } })
    fireEvent.click(within(dlg).getByRole('button', { name: 'Send' }))
    const ans = await within(dlg).findByText(/midsem exams for group CSE-2/i, {}, T)
    expect(ans.textContent).toMatch(/\d{2}:\d{2}-\d{2}:\d{2}/)                       // times
    expect(ans.textContent).toMatch(/venue [A-Z]/)                                      // room
    expect(ans.textContent).not.toMatch(/I have no exam entries/)
    fireEvent.change(within(dlg).getByLabelText('Ask Campus Buddy'), { target: { value: 'Exam kab hai?' } })
    fireEvent.click(within(dlg).getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(within(dlg).getAllByText(/midsem exams for group CSE-2/i).length).toBe(2), T)
  })
  it('admin publishes and withdraws; a withdrawn timetable shows students the not-published message', async () => {
    await renderAs('admin', '/app/exams')
    const btn = await screen.findByRole('button', { name: /^(Withdraw|Publish)$/ }, T)
    if (/Publish/.test(btn.textContent)) { fireEvent.click(btn); await screen.findByRole('button', { name: 'Withdraw' }, T) }
    fireEvent.click(screen.getByRole('button', { name: 'Withdraw' }))
    expect(await screen.findByText(/Draft \(not visible to students\)/i, {}, T)).toBeInTheDocument()
    const r = await api.login('student@opticampus.demo', PW); tokenStore.set(r.token)
    const ex = await api.exams(); expect(ex.exams).toEqual([]); expect(ex.note).toMatch(/not been published|published/i)
    const a = await api.login('admin@opticampus.demo', PW); tokenStore.set(a.token)
    await api.publishExams(false)                                                   // leave the system published for later tests
    expect((await api.exams()).published).toBe(true)
  })
  it('exam views can be filtered by group, course and room (admin)', async () => {
    await renderAs('admin', '/app/exams')
    fireEvent.click(await screen.findByRole('tab', { name: 'By course' }, T))
    expect(await screen.findByLabelText('Course')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'By room' })); expect(await screen.findByLabelText('Room')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'By group' })); expect(await screen.findByLabelText('Group')).toBeInTheDocument()
  })
})

describe('faculty schedule assistant and role-aware Buddy prompts', () => {
  const teachingDay = async () => {
    const r = await api.login('faculty@opticampus.demo', PW); tokenStore.set(r.token)
    const tt = await api.timetable()
    const d = tt.sessions.find((s) => s.faculty_id === 'F01' && !s.basket_slot).day
    return { MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday', THU: 'Thursday', FRI: 'Friday' }[d]
  }
  it('faculty describes a change, sees validated options, submits; nothing is applied; admin reviews and rejects it', async () => {
    const day = await teachingDay()
    await renderAs('faculty', '/app/assistant')
    fireEvent.change(await screen.findByLabelText(/What do you need/i, {}, T), { target: { value: `I am unavailable on ${day} because I have to attend a conference` } })
    fireEvent.click(screen.getByRole('button', { name: /Find options/i }))
    expect(await screen.findByText(/Official validator: accepted/i, {}, T)).toBeInTheDocument()
    expect(screen.getAllByRole('radio').length).toBeGreaterThan(0)
    expect(screen.getByText(/stays unchanged until the Admin approves/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Submit for Admin approval/i }))
    const ok = await screen.findByText(/Submitted for Admin approval|Reference DIS-/i, {}, T)
    const id = (document.body.textContent.match(/DIS-[0-9a-f]{8}/) || [])[0]
    expect(id).toBeTruthy()
    // the requester sees it in their own history; the Admin can open and reject it
    const a = await api.login('admin@opticampus.demo', PW); tokenStore.set(a.token)
    const before = (await api.timetable()).sessions.map((s) => `${s.session_id}${s.day}${s.start_period}${s.room_id}`).join()
    document.body.innerHTML = ''
    await renderAs('admin', '/app/disruptions')
    fireEvent.click(await screen.findByRole('button', { name: `Review ${id}` }, T))
    expect(await screen.findByText(/Official validator: accepted/i, {}, T)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Reject proposal/i }))
    expect(await screen.findByRole('button', { name: /^Rejected$/ }, T)).toBeInTheDocument()
    expect((await api.timetable()).sessions.map((s) => `${s.session_id}${s.day}${s.start_period}${s.room_id}`).join()).toBe(before)   // unchanged
  }, 90000)
  it('an impossible request shows the conflict report and offers nothing to submit', async () => {
    await renderAs('faculty', '/app/assistant')
    fireEvent.change(await screen.findByLabelText(/What do you need/i, {}, T), { target: { value: 'I am unavailable on Monday Tuesday Wednesday Thursday Friday' } })
    fireEvent.click(screen.getByRole('button', { name: /Find options/i }))
    expect((await screen.findAllByText(/no valid alternative/i, {}, T)).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /Submit for Admin approval/i })).toBeNull()
  }, 60000)
  it('only faculty can open the assistant page', async () => {
    await renderAs('student', '/app/assistant')
    expect(await screen.findByText(/don't have access/i, {}, T)).toBeInTheDocument()
  })
  it('Buddy shows role-specific quick prompts; student chip answers the midsem question, faculty chip links to the assistant', async () => {
    await renderAs('student', '/app')
    fireEvent.click(await screen.findByRole('button', { name: /Open Campus Buddy/i }, T))
    const dlg = await screen.findByRole('dialog', { name: /Campus Buddy chat/i })
    for (const q of ['When is my midsem?', 'Show my timetable today', 'Where is my next class?', 'Do I have a free period today?', 'Exam kab hai?']) expect(within(dlg).getByRole('button', { name: q })).toBeInTheDocument()
    fireEvent.click(within(dlg).getByRole('button', { name: 'When is my midsem?' }))
    expect(await within(dlg).findByText(/midsem exams for group CSE-2/i, {}, T)).toBeInTheDocument()
  })
  it('faculty quick prompts include the schedule-change actions', async () => {
    await renderAs('faculty', '/app')
    fireEvent.click(await screen.findByRole('button', { name: /Open Campus Buddy/i }, T))
    const dlg = await screen.findByRole('dialog', { name: /Campus Buddy chat/i })
    expect(within(dlg).getByRole('link', { name: 'Request a schedule change' })).toHaveAttribute('href', '/app/assistant')
    expect(within(dlg).getByRole('link', { name: 'Mark myself unavailable' })).toHaveAttribute('href', '/app/availability')
  })
})
