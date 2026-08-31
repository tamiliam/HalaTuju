import type { Config } from 'tailwindcss'

/** One tone ramp wired to its CSS variables. Values (and the dark reversal) live in globals.css. */
const toneRamp = (tone: string) => Object.fromEntries(
  [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map(
    (stop) => [stop, `rgb(var(--${tone}-${stop}) / <alpha-value>)`],
  ),
)

/**
 * The eight category swatches, three ROLES each (Layer 1 F2c).
 *
 * Gives `bg-category-3-surface`, `text-category-3-ink`, `bg-category-3-dot`. Roles rather than
 * numbered stops because a category colour has no ramp — it is one chip, and its dark values are
 * a role swap (deep surface, pale ink), not the reversal the tones use.
 */
const categorySwatches = Object.fromEntries(
  [1, 2, 3, 4, 5, 6, 7, 8].map((n) => [n, {
    surface: `rgb(var(--category-${n}-surface) / <alpha-value>)`,
    ink: `rgb(var(--category-${n}-ink) / <alpha-value>)`,
    dot: `rgb(var(--category-${n}-dot) / <alpha-value>)`,
  }]),
)

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // Brand colours are RGB-CHANNEL CSS vars (platform Sprint 6, decision D3) so the opacity
      // modifiers in use (/40, /20) work. The channels are defined in globals.css :root as the
      // exact platform hexes; a tenant overrides them at runtime (branding-context). '<alpha-value>'
      // is Tailwind's placeholder for the utility's opacity.
      colors: {
        primary: {
          50: 'rgb(var(--brand-50) / <alpha-value>)',
          100: 'rgb(var(--brand-100) / <alpha-value>)',
          200: 'rgb(var(--brand-200) / <alpha-value>)',
          300: 'rgb(var(--brand-300) / <alpha-value>)',
          400: 'rgb(var(--brand-400) / <alpha-value>)',
          500: 'rgb(var(--brand-500) / <alpha-value>)',
          600: 'rgb(var(--brand-600) / <alpha-value>)',
          700: 'rgb(var(--brand-700) / <alpha-value>)',
          800: 'rgb(var(--brand-800) / <alpha-value>)',
          900: 'rgb(var(--brand-900) / <alpha-value>)',
        },
        // ── Theme tokens (Layer 1 F1) ────────────────────────────────────────
        // Same mechanism as `primary` above, extended to the ground and to the
        // four meanings the product speaks in. Values live in globals.css; the
        // dark set is the light set reversed. See that file for why the ramps
        // keep Tailwind's numbers rather than semantic names.
        //
        // ⚠ `ground` REPLACES `gray` in themed code, but Tailwind's own `gray`
        // stays available on purpose — deleting it would break every unmigrated
        // surface at once, and this arc migrates one surface per sprint. The
        // palette guard test is what stops `gray` creeping back into a surface
        // already converted; the absence of the utility is not the guard.
        ground: {
          0: 'rgb(var(--ground-0) / <alpha-value>)',
          50: 'rgb(var(--ground-50) / <alpha-value>)',
          100: 'rgb(var(--ground-100) / <alpha-value>)',
          200: 'rgb(var(--ground-200) / <alpha-value>)',
          300: 'rgb(var(--ground-300) / <alpha-value>)',
          400: 'rgb(var(--ground-400) / <alpha-value>)',
          500: 'rgb(var(--ground-500) / <alpha-value>)',
          600: 'rgb(var(--ground-600) / <alpha-value>)',
          700: 'rgb(var(--ground-700) / <alpha-value>)',
          800: 'rgb(var(--ground-800) / <alpha-value>)',
          900: 'rgb(var(--ground-900) / <alpha-value>)',
          1000: 'rgb(var(--ground-1000) / <alpha-value>)',
        },
        positive: toneRamp('positive'),
        info: toneRamp('info'),
        caution: toneRamp('caution'),
        critical: toneRamp('critical'),
        // ⚠ NOT a tone. `category-N` MEANS NOTHING — it exists so one field of study, institution
        // type or entry condition can be told from the next. Never use it for a state, and never
        // use a tone for a category: see globals.css and docs/decisions.md.
        category: categorySwatches,

        // Legacy flat semantics — predate the ramps above and are effectively
        // unused (`bg-success`, not `bg-green-500`). Left alone rather than
        // deleted in a sprint that is not about them; the palette guard will
        // surface them if anything starts using them.
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
      },
      fontFamily: {
        // Lexend from Stitch design
        sans: ['Lexend', 'system-ui', 'sans-serif'],
        // IBM Plex Sans — applied to the four ORGANISATION admin modules only
        // (invite / payments / contracts / sources) via `font-plex`.
        plex: ['var(--font-ibm-plex-sans)', 'IBM Plex Sans', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        // 8px rounded corners from Stitch
        DEFAULT: '8px',
        'lg': '12px',
        'xl': '16px',
      },
      keyframes: {
        'slide-in': {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
      },
      animation: {
        'slide-in': 'slide-in 0.2s ease-out',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}

export default config
