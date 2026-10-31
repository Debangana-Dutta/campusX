// The official OptiCampus logo (supplied by the team): frontend/src/assets/logo.png.
// The artwork is on a white background, so it sits in a round white badge to look correct in both light and dark themes.
const found = import.meta.glob('../assets/logo.{svg,png,webp}', { eager: true, query: '?url', import: 'default' })
const src = Object.values(found)[0]

export function LogoMark({ size = 40, className = '' }) {
  if (!src) return null
  return (
    <span className={`inline-block shrink-0 overflow-hidden rounded-full bg-white shadow-[0_2px_8px_rgba(60,60,120,.25)] ${className}`} style={{ width: size, height: size }}>
      <img src={src} width={size} height={size} alt="OptiCampus logo" className="h-full w-full object-contain" />
    </span>
  )
}
export function Wordmark({ className = '' }) {
  return <span className={`text-xl font-bold tracking-tight text-navy ${className}`}>OptiCampus</span>
}
export function Logo({ size = 40, showWord = true }) {
  return <span className="inline-flex items-center gap-2.5"><LogoMark size={size} />{showWord && <Wordmark />}</span>
}
