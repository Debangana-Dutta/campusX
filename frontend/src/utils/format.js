export const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']
export const DAY_NAMES = { MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday', THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday', SUN: 'Sunday' }
export const PERIOD_TIME = { 1: '08:00', 2: '09:00', 3: '10:00', 4: '11:00', 5: '12:00', 6: '14:00', 7: '15:00', 8: '16:00', 9: '17:00', 10: '18:00', 11: '19:00', 12: '20:00', 13: '21:00' }
export const periodEnd = (p) => { const [h] = PERIOD_TIME[p].split(':'); return `${String(+h + 1).padStart(2, '0')}:00` }
export const span = (a, b) => `${PERIOD_TIME[a]}-${periodEnd(b)}`
export const titleCase = (s = '') => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

// restrained pastel course colours (same set in light/dark; text colour comes from CSS vars)
const PALETTE = ['bg-lavender/70', 'bg-mint/70', 'bg-peach/70', 'bg-peri/70', 'bg-sky/70', 'bg-rose/70']
export const courseColor = (id = '') => { let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0; return PALETTE[h % PALETTE.length] }

export function toCsv(rows) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const head = Object.keys(rows[0] || {})
  return [head.map(esc).join(','), ...rows.map((r) => head.map((k) => esc(r[k])).join(','))].join('\n')
}
export function download(name, text, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
}
export const RULE_TEXT = {
  H1: 'A session is missing, duplicated, or placed outside the teaching week',
  H2: 'A faculty member is in two places at once',
  H3: 'A student group is in two places at once',
  H4: 'A room is double-booked',
  H5: 'Room is too small for the session or exam',
  H6: 'Room type does not match what the session needs',
  H7: 'Faculty unavailability is violated',
  H8: 'Room unavailability (maintenance) is violated',
  H9: 'Lunch / lab-start / period-range rule is violated',
  H10: 'A session needing an accessible room is not in one',
  H11: 'Elective basket sessions are not at the same time',
  H12: 'A faculty member exceeds their daily teaching limit',
  H13: 'A booking clashes with a class, another booking, a closure or a mandatory group',
  H14: 'A fixed-slot session was moved',
  B1: 'Booking decision is missing, duplicated or has an unknown status',
  B2: 'A class was displaced by something not allowed to displace it',
  B3: 'A cancelled request was approved',
  E1: 'An exam is missing, duplicated or in an invalid slot',
  E2: 'An exam uses a room that cannot host exams',
}
