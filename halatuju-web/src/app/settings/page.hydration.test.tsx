/**
 * @jest-environment jsdom
 *
 * TD-388: /settings, /onboarding/grades and /onboarding/stpm-grades must render the language of the
 * WORDS on screen (contentLocale, English on the first render), never the stored choice (locale) —
 * the server renders English, so a stored Tamil choice made the first client render differ (React #425).
 */
import { render, screen } from '@testing-library/react'
import { readFileSync } from 'fs'
import { join } from 'path'

import SettingsPage from './page'

jest.mock('@/lib/i18n', () => ({
  // A reader with Tamil stored, whose catalogue has not landed: choice is ta, words are en.
  useT: () => ({ t: (k: string) => k, locale: 'ta', contentLocale: 'en' }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'Tamil-label' },
}))
jest.mock('@/components/LanguageSelector', () => () => null)
jest.mock('@/components/ThemeSelector', () => () => null)
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)

describe('TD-388 hydration-safe locale', () => {
  it('settings shows the language of the words on screen, not the stored choice', () => {
    render(<SettingsPage />)
    expect(screen.getByText('English')).toBeTruthy()
    expect(screen.queryByText('Tamil-label')).toBeNull()
  })

  it.each([
    'onboarding/grades/page.tsx',
    'onboarding/stpm-grades/page.tsx',
    'settings/page.tsx',
  ])('%s reads contentLocale and never the bare stored locale', (file) => {
    const src = readFileSync(join(__dirname, '..', file), 'utf8')
    expect(src).not.toMatch(/\{[^}]*\blocale\b[^}]*\}\s*=\s*useT\(\)/)
    expect(src).not.toMatch(/,\s*locale\)/)
  })
})
