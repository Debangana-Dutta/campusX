// Central API service. The ONLY place that knows the backend URL (VITE_API_BASE_URL). No secrets live here:
// Gemini and Supabase service-role keys exist only on the backend.
const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const TOKEN_KEY = 'cx-token'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  constructor(status, message, detail) { super(message); this.status = status; this.detail = detail }
}

async function request(path, { method = 'GET', body, auth = true, raw = false } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const t = tokenStore.get()
  if (auth && t) headers.Authorization = `Bearer ${t}`
  let res
  try {
    res = await fetch(`${BASE}/api${path}`, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  } catch {
    throw new ApiError(0, 'Cannot reach the Campus X server. Check your connection or try again shortly.')
  }
  if (res.status === 401 && auth) window.dispatchEvent(new Event('cx-unauthorized'))
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    const e = data?.error
    throw new ApiError(res.status, (typeof e?.message === 'string' && e.message) || data?.detail || `Request failed (${res.status})`, e?.detail ?? data)
  }
  return raw ? res : data
}

const q = (o) => { const p = new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== null)); return p.toString() ? `?${p}` : '' }

export const api = {
  health: () => request('/health', { auth: false }),
  login: (username, password) => request('/auth/local-login', { method: 'POST', body: { username, password }, auth: false }),
  me: () => request('/auth/me'),
  datasetStatus: () => request('/dataset/status', { auth: false }),
  datasetSummary: () => request('/dataset/summary'),
  summary: () => request('/admin/summary'),
  analytics: () => request('/reports/analytics'),
  utilisation: () => request('/reports/room-utilisation'),
  timetable: () => request('/timetable'),
  groupTimetable: (g) => request(`/timetable/group/${g}`),
  generate: (body) => request('/timetable/generate', { method: 'POST', body }),
  approve: () => request('/timetable/approve', { method: 'POST' }),
  validate: () => request('/timetable/validate', { method: 'POST' }),
  exportSchedule: () => request('/timetable/export'),
  venues: () => request('/venues'),
  events: () => request('/events'),
  exams: () => request('/exams'),
  generateExams: () => request('/exams/generate', { method: 'POST' }),
  bookings: () => request('/bookings'),
  booking: (id) => request(`/bookings/${id}`),
  parseBooking: (text) => request('/bookings/parse', { method: 'POST', body: { text } }),
  createBooking: (b) => request('/bookings', { method: 'POST', body: b }),
  decideBooking: (id, b) => request(`/bookings/${id}/decision`, { method: 'POST', body: b }),
  respondBooking: (id, accept) => request(`/bookings/${id}/respond`, { method: 'POST', body: { accept } }),
  cancelBooking: (id) => request(`/bookings/${id}/cancel`, { method: 'POST' }),
  disruptions: () => request('/disruptions'),
  sampleDisruption: () => request('/disruptions/sample'),
  previewDisruption: (changes, time_limit_s = 90) => request('/disruptions/preview', { method: 'POST', body: { changes, time_limit_s } }),
  disruptionComparison: (id) => request(`/disruptions/${id}/comparison`),
  applyDisruption: (id) => request(`/disruptions/apply${q({ did: id })}`, { method: 'POST' }),
  notifications: () => request('/notifications'),
  markRead: (ids) => request('/notifications/read', { method: 'POST', body: { ids } }),
  announce: (message, audience) => request('/notifications/announce', { method: 'POST', body: { message, audience } }),
  ask: (question, extra = {}) => request('/buddy/ask', { method: 'POST', body: { question, ...extra } }),
  aiStatus: () => request('/ai/status'),
  users: () => request('/admin/users'),
  assignRole: (user_id, role) => request('/admin/role-assignments', { method: 'POST', body: { user_id, role } }),
  audit: () => request('/admin/audit'),
  demoReset: () => request('/admin/demo-reset', { method: 'POST' }),
}
