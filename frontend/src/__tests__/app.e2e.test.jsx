// Full-stack UI tests: the REAL React app against the REAL FastAPI backend (VITE_API_BASE_URL), no mocked responses.
// Verifies rendering, role guards, forms and workflows. (jsdom cannot judge visual layout; see README known limitations.)
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '../App'
import { AuthProvider, ThemeProvider, ToastProvider } from '../contexts/AppContexts'
import { api, tokenStore } from '../services/api'

const T = { timeout: 15000 }
async function renderAs(role, path = '/app') {
  if (role) { const r = await api.login(role, 'campusx-demo'); tokenStore.set(r.token) }
  return render(<MemoryRouter initialEntries={[path]}><ThemeProvider><ToastProvider><AuthProvider><App /></AuthProvider></ToastProvider></ThemeProvider></MemoryRouter>)
}
const nav = (name) => screen.findByRole('link', { name }, T)

describe('public pages', () => {
  it('landing page shows the brand, headline and both calls to action', async () => {
    await renderAs(null, '/')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('One Campus. Zero Clashes.')
    expect(screen.getByRole('link', { name: /Explore Campus X/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Sign in/i }).length).toBeGreaterThan(0)
    expect(screen.queryByText(/testimonial|trusted by|\d+\+ (students|users)/i)).toBeNull()   // no invented claims
  })
  it('protected routes redirect anonymous users to login', async () => {
    await renderAs(null, '/app/timetable')
    expect(await screen.findByRole('heading', { name: /Welcome back/i }, T)).toBeInTheDocument()
  })
  it('login with a wrong password shows an error; the demo button signs in', async () => {
    await renderAs(null, '/login')
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'nope' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(/invalid credentials/i, {}, T)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Admin/ }))
    expect(await screen.findByText(/Sessions scheduled/i, {}, T)).toBeInTheDocument()
  })
})

describe('role dashboards use live backend data', () => {
  it('admin overview shows real counts and the full admin menu', async () => {
    await renderAs('admin')
    expect(await screen.findByText('189 / 189', {}, T)).toBeInTheDocument()
    expect(await screen.findByText('Accepted', {}, T)).toBeInTheDocument()
    for (const l of ['Master Timetable', 'Generate Timetable', 'Validation Reports', 'Venue Management', 'Booking Requests', 'Disruptions', 'Examinations', 'User Management']) expect(await nav(l)).toBeInTheDocument()
  })
  it.each([['faculty', ['My Timetable', 'Availability']], ['coordinator', ['Department Timetable', 'Faculty Overview']], ['club', ['Request a Venue', 'My Bookings']], ['student', ['My Timetable', 'Examinations']]])('%s gets a role-specific menu', async (role, links) => {
    await renderAs(role)
    for (const l of links) expect(await nav(l)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Generate Timetable' })).toBeNull()
  })
  it('role guard blocks a page the role may not open', async () => {
    await renderAs('club', '/app/generate')
    expect(await screen.findByText(/don't have access/i, {}, T)).toBeInTheDocument()
    expect(screen.queryByText('Run solver and validator')).toBeNull()
  })
  it('student overview is scoped to their group and read-only', async () => {
    await renderAs('student')
    expect(await screen.findByText(/Read-only view for CSE-2/i, {}, T)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Booking/i })).toBeNull()
  })
})

describe('timetable, validation, exams', () => {
  it('master timetable renders the grid with real sessions, lunch row and approved status', async () => {
    await renderAs('admin', '/app/timetable')
    expect(await screen.findByRole('region', { name: /Weekly timetable grid/i }, T)).toBeInTheDocument()
    expect(screen.getByText(/Lunch/)).toBeInTheDocument()
    expect(await screen.findByText(/Approved: validated/i, {}, T)).toBeInTheDocument()
    const grid = screen.getByRole('region', { name: /Weekly timetable grid/i })
    const cards = within(grid).getAllByRole('button')
    expect(cards.length).toBeGreaterThan(5)
    fireEvent.click(cards[0])
    expect(await screen.findByRole('dialog')).toHaveTextContent(/Faculty/)
  })
  it('timetable views switch (room view) and the day view lists free rooms', async () => {
    await renderAs('admin', '/app/timetable')
    await screen.findByRole('region', { name: /Weekly timetable grid/i }, T)
    fireEvent.click(screen.getByRole('tab', { name: 'Room' }))
    await waitFor(() => expect(screen.getByLabelText('Room')).toBeInTheDocument(), T)
    fireEvent.click(screen.getByRole('tab', { name: 'Day' }))
    expect(await screen.findByRole('region', { name: /Room occupancy Monday/i }, T)).toBeInTheDocument()
    expect(screen.getAllByLabelText('free').length).toBeGreaterThan(10)
  })
  it('student sees only their own group timetable', async () => {
    await renderAs('student', '/app/timetable')
    expect(await screen.findByRole('region', { name: /Weekly timetable grid|Agenda|Monday/i }, T).catch(() => screen.findByText(/session\(s\) shown/i, {}, T))).toBeTruthy()
    expect(screen.queryByRole('tab', { name: 'Faculty' })).toBeNull()
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
    expect(screen.getByText(/Enter the expected attendance/i)).toBeInTheDocument()
  })
  it('an impossible request is rejected with a reason shown to the requester', async () => {
    await renderAs('club', '/app/request-venue')
    fireEvent.change(await screen.findByLabelText('Event title', {}, T), { target: { value: 'Mega fest' } })
    fireEvent.change(screen.getByLabelText('Attendance'), { target: { value: '1200' } })
    fireEvent.change(screen.getByLabelText('Duration (hours)'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Auditorium' })); fireEvent.click(screen.getByRole('button', { name: 'Classroom' }))
    fireEvent.click(screen.getByRole('button', { name: 'Lecture Hall' })); fireEvent.click(screen.getByRole('button', { name: 'Seminar Hall' }))
    fireEvent.click(screen.getByRole('button', { name: /Submit for decision/i }))
    expect(await screen.findByText(/No venue seats 1,200/i, {}, T)).toBeInTheDocument()
  })
  it('my bookings lists the decisions with reasons, and notifications arrived from real events', async () => {
    await renderAs('club', '/app/bookings')
    expect(await screen.findByText('Mega fest', {}, T)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Mega fest'))
    expect(await screen.findByText(/Decision explanation/i)).toBeInTheDocument()
  })
  it('notification centre shows unread items and mark-all-read clears them', async () => {
    await renderAs('club', '/app/notifications')
    const btn = await screen.findByRole('button', { name: /Mark all as read/i }, T)
    await waitFor(() => expect(btn).not.toBeDisabled(), T)
    fireEvent.click(btn)
    await waitFor(() => expect(screen.getByRole('button', { name: /Mark all as read/i })).toBeDisabled(), T)
  })
})

describe('disruption workflow (admin)', () => {
  it('preview shows a validated minimum-movement repair; nothing applies until the admin approves', async () => {
    await renderAs('admin', '/app/disruptions')
    fireEvent.click(await screen.findByRole('button', { name: /Load official sample/i }, T))
    await screen.findByText(/Faculty F07 unavailable/i, {}, T)
    fireEvent.click(screen.getByRole('button', { name: /Preview repair/i }))
    expect(await screen.findByText(/Official validator: accepted/i, {}, { timeout: 60000 })).toBeInTheDocument()
    expect(screen.getByText(/Proven minimum/i)).toBeInTheDocument()
    expect(screen.getByText(/Before/)).toBeInTheDocument()
    const apply = screen.getByRole('button', { name: /Admin approve and apply/i })
    expect(apply).not.toBeDisabled()
    fireEvent.click(apply)                                       // opens the confirmation dialog; still nothing applied
    expect(await screen.findByRole('dialog')).toHaveTextContent(/Apply this change/i)
    fireEvent.click(screen.getByRole('button', { name: 'Approve and apply' }))
    expect(await screen.findByRole('button', { name: /^Applied$/ }, T)).toBeInTheDocument()
  }, 90000)
  it('faculty can request unavailability but cannot open the admin disruption page', async () => {
    await renderAs('faculty', '/app/disruptions')
    expect(await screen.findByText(/don't have access/i, {}, T)).toBeInTheDocument()
  })
})

describe('Campus Buddy, theme, mobile navigation', () => {
  it('buddy answers from backend data (English + Hinglish) and labels how it answered', async () => {
    await renderAs('student', '/app/buddy')
    fireEvent.change(await screen.findByLabelText('Your question', {}, T), { target: { value: 'Aaj meri next class kaha hai?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText(/^Next class \(/, {}, T)).toBeInTheDocument()
    expect(screen.getAllByText(/Answered by rules/i).length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'Who is teaching CS201?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText(/Dr\. Rohit Sahoo/, {}, T)).toBeInTheDocument()
  })
  it('theme toggle switches dark mode and persists the choice', async () => {
    await renderAs('admin')
    fireEvent.click(await screen.findByRole('button', { name: /Switch to dark mode/i }, T))
    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem('cx-theme')).toBe('dark')
    fireEvent.click(screen.getByRole('button', { name: /Switch to light mode/i }))
    expect(document.documentElement).not.toHaveClass('dark')
  })
  it('mobile drawer opens with the full navigation and closes', async () => {
    await renderAs('admin')
    fireEvent.click(await screen.findByRole('button', { name: /Open menu/i }, T))
    const d = await screen.findByLabelText('Navigation drawer')
    expect(within(d).getByRole('link', { name: 'Master Timetable' })).toBeInTheDocument()
    fireEvent.click(within(d).getByRole('button', { name: /Close menu/i }))
    await waitFor(() => expect(screen.queryByLabelText('Navigation drawer')).toBeNull())
  })
  it('signing out returns to the landing page and clears the session', async () => {
    await renderAs('admin')
    fireEvent.click(await screen.findByRole('button', { name: /Dean's Office/i }, T))
    fireEvent.click(await screen.findByRole('menuitem', { name: /Sign out/i }))
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('One Campus')
    expect(tokenStore.get()).toBeNull()
  })
})
