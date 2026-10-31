import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Guard from './routes/Guard'
import AppShell from './layouts/AppShell'
import { LoadingBlock } from './components/ui'
import Landing from './pages/Landing'
import Login from './pages/Login'

const P = (f) => lazy(f)
const Overview = P(() => import('./pages/Overview'))
const Timetable = P(() => import('./pages/Timetable'))
const Generate = P(() => import('./pages/Generate'))
const Validation = P(() => import('./pages/Validation'))
const Venues = P(() => import('./pages/Venues'))
const Bookings = P(() => import('./pages/Bookings'))
const RequestVenue = P(() => import('./pages/RequestVenue'))
const Disruptions = P(() => import('./pages/Disruptions'))
const Exams = P(() => import('./pages/Exams'))
const Analytics = P(() => import('./pages/Analytics'))
const Users = P(() => import('./pages/Users'))
const Notifications = P(() => import('./pages/Notifications'))
const Buddy = P(() => import('./pages/Buddy'))
const Settings = P(() => import('./pages/Settings'))
const Availability = P(() => import('./pages/Availability'))
const Events = P(() => import('./pages/Events'))
const Classes = P(() => import('./pages/Classes'))
const FacultyOverview = P(() => import('./pages/FacultyOverview'))

const A = ['admin']
const STAFF = ['admin', 'faculty', 'department_coordinator', 'club_representative']
const route = (path, El, roles) => <Route path={path} element={<Guard roles={roles}><El /></Guard>} />

export default function App() {
  return (
    <Suspense fallback={<div className="p-8"><LoadingBlock /></div>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/app" element={<Guard><AppShell /></Guard>}>
          {route('', Overview)}
          {route('timetable', Timetable)}
          {route('generate', Generate, A)}
          {route('validation', Validation, ['admin', 'department_coordinator'])}
          {route('venues', Venues, STAFF)}
          {route('bookings', Bookings, STAFF)}
          {route('request-venue', RequestVenue, ['admin', 'department_coordinator', 'club_representative'])}
          {route('disruptions', Disruptions, A)}
          {route('exams', Exams)}
          {route('analytics', Analytics, STAFF)}
          {route('users', Users, A)}
          {route('notifications', Notifications)}
          {route('buddy', Buddy)}
          {route('settings', Settings)}
          {route('availability', Availability, ['faculty'])}
          {route('events', Events)}
          {route('classes', Classes, ['faculty'])}
          {route('faculty', FacultyOverview, ['department_coordinator', 'admin'])}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
