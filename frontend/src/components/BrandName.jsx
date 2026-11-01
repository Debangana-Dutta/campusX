/** The OptiCampus name in the display serif, two-tone like the logo. */
export default function BrandName({ className = '', stacked = false }) {
  return (
    <span className={`brand-name ${stacked ? 'block' : ''} ${className}`}>
      <span className="text-navy">Opti</span>{stacked && <br />}<span className="brand-gradient">Campus</span>
    </span>
  )
}
