// Campus X identity: an X made of four calendar-slot tiles joined through a central node
// (the "one campus, no clashes" idea: separate slots resolved into one intersection).
export function LogoMark({ size = 40, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} role="img" aria-label="Campus X">
      <defs>
        <linearGradient id="cxg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#cdb8ff" /><stop offset="1" stopColor="#b9c6ff" /></linearGradient>
        <filter id="cxs" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="2" dy="3" stdDeviation="2" floodColor="#7e90c4" floodOpacity=".45" /></filter>
      </defs>
      <rect width="64" height="64" rx="19" fill="url(#cxg)" filter="url(#cxs)" />
      <g fill="#1b2559">
        <rect x="11" y="11" width="15" height="15" rx="5" /><rect x="38" y="11" width="15" height="15" rx="5" />
        <rect x="11" y="38" width="15" height="15" rx="5" /><rect x="38" y="38" width="15" height="15" rx="5" />
      </g>
      <path d="M24 24 L40 40 M40 24 L24 40" stroke="#1b2559" strokeWidth="6" strokeLinecap="round" />
      <circle cx="32" cy="32" r="6.5" fill="#bfebd7" stroke="#1b2559" strokeWidth="3" />
    </svg>
  )
}
export function Wordmark({ className = '' }) {
  return <span className={`text-xl font-extrabold tracking-tight text-navy ${className}`}>Campus<span className="text-accent"> X</span></span>
}
export function Logo({ size = 40, showWord = true }) {
  return <span className="inline-flex items-center gap-2.5"><LogoMark size={size} />{showWord && <Wordmark />}</span>
}
