import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // HalaTuju brand colors from Stitch design
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#137fec', // Main brand color from Stitch
          600: '#1066c2',
          700: '#0d4f99',
          800: '#0a3970',
          900: '#072347',
        },
        // Semantic colors
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
      },
      fontFamily: {
        // Lexend from Stitch design
        sans: ['Lexend', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        // 8px rounded corners from Stitch
        DEFAULT: '8px',
        'lg': '12px',
        'xl': '16px',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}

export default config
