import { Bell, BarChart3, Bot, Building2, CalendarClock, CalendarDays, CalendarRange, CalendarX2, ClipboardCheck, GraduationCap, Home, LayoutDashboard, MapPinned, Megaphone, PartyPopper, Settings, ShieldCheck, Users, Wand2, UserRound, FilePlus2 } from 'lucide-react'

// Navigation per role. UI hiding is convenience only: every endpoint enforces roles on the backend.
const common = [{ to: '/app/notifications', label: 'Notifications', icon: Bell }, { to: '/app/buddy', label: 'Campus Buddy', icon: Bot }]
export const NAV = {
  admin: [
    { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/app/timetable', label: 'Master Timetable', icon: CalendarDays },
    { to: '/app/generate', label: 'Generate Timetable', icon: Wand2 },
    { to: '/app/validation', label: 'Validation Reports', icon: ShieldCheck },
    { to: '/app/venues', label: 'Venue Management', icon: Building2 },
    { to: '/app/bookings', label: 'Booking Requests', icon: ClipboardCheck },
    { to: '/app/request-venue', label: 'Request a Venue', icon: FilePlus2 },
    { to: '/app/disruptions', label: 'Disruptions', icon: CalendarX2 },
    { to: '/app/exams', label: 'Examinations', icon: GraduationCap },
    { to: '/app/analytics', label: 'Room Utilisation', icon: BarChart3 },
    { to: '/app/users', label: 'User Management', icon: Users },
    ...common, { to: '/app/settings', label: 'Settings', icon: Settings },
  ],
  faculty: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/timetable', label: 'My Timetable', icon: CalendarDays },
    { to: '/app/classes', label: 'My Classes', icon: CalendarRange },
    { to: '/app/availability', label: 'Availability', icon: CalendarClock },
    ...common, { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
  department_coordinator: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/timetable', label: 'Department Timetable', icon: CalendarDays },
    { to: '/app/faculty', label: 'Faculty Overview', icon: Users },
    { to: '/app/bookings', label: 'Booking Requests', icon: ClipboardCheck },
    { to: '/app/request-venue', label: 'Book a Room', icon: FilePlus2 },
    { to: '/app/validation', label: 'Scheduling Conflicts', icon: ShieldCheck },
    { to: '/app/venues', label: 'Venues', icon: Building2 },
    ...common, { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
  club_representative: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/request-venue', label: 'Request a Venue', icon: FilePlus2 },
    { to: '/app/bookings', label: 'My Bookings', icon: ClipboardCheck },
    { to: '/app/events', label: 'Events', icon: PartyPopper },
    { to: '/app/venues', label: 'Venues', icon: MapPinned },
    ...common, { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
  student: [
    { to: '/app', label: 'Overview', icon: Home, end: true },
    { to: '/app/timetable', label: 'My Timetable', icon: CalendarDays },
    { to: '/app/buddy', label: 'Campus Buddy', icon: Bot },
    { to: '/app/exams', label: 'Examinations', icon: GraduationCap },
    { to: '/app/events', label: 'Campus Events', icon: Megaphone },
    { to: '/app/notifications', label: 'Notifications', icon: Bell },
    { to: '/app/settings', label: 'Profile', icon: UserRound },
  ],
}
export const ROLE_LABEL = { admin: 'Admin (Dean\'s office)', faculty: 'Faculty', department_coordinator: 'Department coordinator', club_representative: 'Club representative', student: 'Student (read-only)' }
