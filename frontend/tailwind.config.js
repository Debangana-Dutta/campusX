/** Claymorphism tokens live in CSS variables (src/styles/index.css) so light/dark share one component set. */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: 'rgb(var(--navy) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        base: 'rgb(var(--base) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        lavender: 'rgb(var(--lavender) / <alpha-value>)',
        mint: 'rgb(var(--mint) / <alpha-value>)',
        peach: 'rgb(var(--peach) / <alpha-value>)',
        peri: 'rgb(var(--peri) / <alpha-value>)',
        sky: 'rgb(var(--sky) / <alpha-value>)',
        rose: 'rgb(var(--rose) / <alpha-value>)',
        accent: 'rgb(var(--accent) / <alpha-value>)',
        ok: 'rgb(var(--ok) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        bad: 'rgb(var(--bad) / <alpha-value>)',
      },
      borderRadius: { clay: '1.5rem', 'clay-sm': '1rem', 'clay-xs': '0.75rem' },
      fontFamily: { sans: ['ui-rounded', '"SF Pro Rounded"', 'Nunito', '"Segoe UI"', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
}
