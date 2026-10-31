import { MessageSquareText, Bell, BarChart3, Building2, CalendarClock, CalendarDays, CalendarX2, ClipboardCheck, Database, GraduationCap, HelpCircle, Home, LayoutDashboard, MapPinned, PartyPopper, Settings, ShieldCheck, Users, Wand2, UserRound, FilePlus2, CalendarRange } from 'lucide-react'

// Navigation per role. UI hiding is convenience only: every endpoint enforces roles on the backend.
const common = [{ to: '/app/notifications', label: 'Notifications', icon: Bell }, { to: '/app/faq', label: 'FAQs', icon: HelpCircle }]
export const NAV = {
  admin: [
    { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/app/timetable', label: 'Timetable', icon: CalendarDays },
    { to: '/app/generate', label: 'Timetable Generator', icon: Wand2 },
    { to: '/app/validation', label: 'Validation', icon: ShieldCheck },
    { to: '/app/bookings', label: 'Requests to Review', icon: ClipboardCheck },
    { to: '/app/request-venue', label: 'Room Booking', icon: FilePlus2 },
    { to: '/app/disruptions', label: 'Schedule Changes', icon: CalendarX2 },
    { to: '/app/exams', label: 'Exams', icon: GraduationCap },
    { to: '/app/venues', label: 'Rooms', icon: Building2 },
    { to: '/app/analytics', label: 'Room Usage', icon: BarChart3 },
    { to: '/app/data', label: 'Data', icon: Database },
    { to: '/app/users', label: 'Users', icon: Users },
    ...common, { to: '/app/settings', label: 'Settings', icon: Settings },
  ],
  faculty: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/timetable', label: 'My Timetable', icon: CalendarDays },
    { to: '/app/classes', label: 'My Classes', icon: CalendarRange },
    { to: '/app/assistant', label: 'Schedule Assistant', icon: MessageSquareText },
    { to: '/app/availability', label: 'Availability', icon: CalendarClock },
    { to: '/app/request-venue', label: 'Room Booking', icon: FilePlus2 },
    { to: '/app/bookings', label: 'My Requests', icon: ClipboardCheck },
    ...common, { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
  department_coordinator: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/timetable', label: 'Department Timetable', icon: CalendarDays },
    { to: '/app/faculty', label: 'Faculty', icon: Users },
    { to: '/app/bookings', label: 'Requests to Review', icon: ClipboardCheck },
    { to: '/app/request-venue', label: 'Room Booking', icon: FilePlus2 },
    { to: '/app/validation', label: 'Conflicts', icon: ShieldCheck },
    { to: '/app/venues', label: 'Rooms', icon: Building2 },
    ...common, { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
  club_representative: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/request-venue', label: 'Request a Venue', icon: FilePlus2 },
    { to: '/app/bookings', label: 'My Bookings', icon: ClipboardCheck },
    { to: '/app/events', label: 'Events', icon: PartyPopper },
    { to: '/app/venues', label: 'Rooms', icon: MapPinned },
    ...common, { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
  student: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/timetable', label: 'My Timetable', icon: CalendarDays },
    { to: '/app/exams', label: 'Exams', icon: GraduationCap },
    { to: '/app/events', label: 'Events', icon: PartyPopper },
    ...common, { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
}
export const ROLE_LABEL = { admin: "Admin (Dean's Office)", faculty: 'Faculty', department_coordinator: 'Department Coordinator', club_representative: 'Club Representative', student: 'Student (read-only)' }
