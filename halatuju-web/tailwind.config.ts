import type { Config } from 'tailwindcss'

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
        // Semantic colors (stay literal — not brand-themed)
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
