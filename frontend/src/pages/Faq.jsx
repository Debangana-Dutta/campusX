import { useMemo, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { PageHeader } from '../components/ui'

const FAQ = [
  ['Timetables', 'Where can I see my timetable?', 'Open Timetable in the menu. Students see their group, faculty see their own classes, and admins and coordinators can switch between group, faculty, room and course views.'],
  ['Timetables', 'Why does my timetable say "Validated" or "Approved"?', 'Validated means the official validator found no clashes. Approved means the admin office has also approved it. Only validated or approved timetables show the verification note.'],
  ['Timetables', 'Why was a class placed at a certain time or room?', 'Open Campus Buddy and ask, for example, "Why is CS201 at 8 AM?". The answer is built from the real schedule: available slots, room fit, faculty preferences and gaps for the group.'],
  ['Examinations', 'When and where are my exams?', 'Open Examinations. Each exam shows its day, slot, and rooms. Exams in a room use half of that room\'s normal capacity, so large exams can use several rooms.'],
  ['Room availability', 'How do I find a free room?', 'Open Rooms, choose a day and period under "Free on / At period", and add filters for capacity or features. The Timetable page also has a Day view showing every room by period.'],
  ['Venue requests', 'How do I request a venue?', 'Open Request a Venue. Describe the event in English or Hinglish and press Understand my request, then check and edit the details before submitting. You can also fill the form by hand.'],
  ['Venue requests', 'Can I cancel a request?', 'Yes. Open My Bookings, select the request and choose Cancel booking. Cancelled requests are never approved.'],
  ['Booking decisions', 'How are booking conflicts decided?', 'By fixed priority: exams, regular classes, institute events, guest lectures, department events, then club events. Requests of equal priority go to whoever submitted first. Your role limits the highest category you can claim.'],
  ['Booking decisions', 'Why was my request rejected or given an alternative?', 'Every decision shows its reason, for example no room is large enough, the room is closed, or a higher-priority booking holds it. An alternative is a different time that meets all your needs; you can accept or decline it.'],
  ['Schedule changes', 'What happens when a teacher is on leave or a room closes?', 'An admin loads the change under Schedule Changes. The system proposes the smallest set of moves, shows exactly what changes, and nothing is applied until an admin approves it.'],
  ['Schedule changes', 'How do faculty report unavailability?', 'Open Availability, choose the days and periods, and send the request. It goes to the admin office for review; you cannot approve your own request.'],
  ['Notifications', 'Who receives notifications?', 'Only the people a message is meant for: you, your role, or everyone for campus-wide announcements. Use Mark all as read to clear the unread count.'],
  ['Account access', 'How do I get an account?', 'Choose Request access on the sign-in page. An administrator reviews the request, and you can sign in once it is approved. Admin accounts are created only by an existing administrator.'],
  ['Account access', 'I forgot my password.', 'Choose Forgot password on the sign-in page. If the email is registered, a single-use link valid for 30 minutes is sent. For privacy, the page looks the same whether or not the email exists.'],
]

export default function Faq() {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(null)
  const items = useMemo(() => FAQ.filter(([c, a, b]) => !q.trim() || `${c} ${a} ${b}`.toLowerCase().includes(q.toLowerCase())), [q])
  const groups = [...new Set(items.map((i) => i[0]))]
  return (
    <>
      <PageHeader title="FAQs" subtitle="Quick answers about timetables, rooms, bookings and your account." />
      <div className="relative mb-5 max-w-md"><label htmlFor="faq-s" className="sr-only">Search FAQs</label><Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input id="faq-s" className="field !pl-10" placeholder="Search questions" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {items.length === 0 ? <p className="clay-inset px-4 py-8 text-center text-muted">No questions match &ldquo;{q}&rdquo;.</p> : groups.map((g) => (
        <section key={g} className="mb-6" aria-label={g}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{g}</h2>
          <div className="grid gap-2">{items.filter((i) => i[0] === g).map(([, a, b]) => {
            const id = `${g}-${a}`, isOpen = open === id
            return (
              <div key={id} className="clay-sm">
                <button className="flex min-h-[48px] w-full items-center justify-between gap-3 px-4 py-3 text-left font-semibold text-navy" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : id)}>{a}<ChevronDown className={`h-5 w-5 shrink-0 text-muted transition ${isOpen ? 'rotate-180' : ''}`} /></button>
                {isOpen && <p className="px-4 pb-4 text-sm leading-relaxed text-ink">{b}</p>}
              </div>)
          })}</div>
        </section>))}
    </>
  )
}
