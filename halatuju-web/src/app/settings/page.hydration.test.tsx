/**
 * @jest-environment jsdom
 *
 * TD-388: /settings, /onboarding/grades and /onboarding/stpm-grades must render the language of the
 * WORDS on screen (contentLocale, English on the first render), never the stored choice (locale) —
 * the server renders English, so a stored Tamil choice made the first client render differ (React #425).
 *
 * All three are RENDERED here with a reader whose stored choice is Tamil but whose catalogue has not
 * landed (choice ta, words en), and the words on screen are read back. A page that fell back to the
 * bare `locale` would paint Tamil (settings label) or Malay / Tamil subject names (the onboarding
 * pages) and fail. This replaces the old source-text scan for `locale` in the three files.
 */
import { render, screen } from '@testing-library/react'

import SettingsPage from './page'
import GradesInputPage from '../onboarding/grades/page'
import StpmGradesPage from '../onboarding/stpm-grades/page'
import { KEY_STPM_STREAM } from '@/lib/storage'

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/onboarding',
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))
jest.mock('@/lib/i18n', () => ({
  // A reader with Tamil stored, whose catalogue has not landed: choice is ta, words are en.
  useT: () => ({ t: (k: string) => k, locale: 'ta', contentLocale: 'en' }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'Tamil-label' },
}))
jest.mock('@/lib/api', () => ({
  calculateMerit: jest.fn().mockResolvedValue({ academic_merit: 80, final_merit: 85 }),
  calculateCgpa: jest.fn().mockResolvedValue({ cgpa: null, counted: [], overall: null, merit_percent: null }),
  getProfile: jest.fn().mockResolvedValue({}),
}))
jest.mock('@/components/LanguageSelector', () => () => null)
jest.mock('@/components/ThemeSelector', () => () => null)
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/ProgressStepper', () => ({ __esModule: true, default: () => null }))

beforeEach(() => localStorage.clear())

describe('TD-388 hydration-safe locale', () => {
  it('settings shows the language of the words on screen, not the stored choice', () => {
    render(<SettingsPage />)
    expect(screen.getByText('English')).toBeTruthy()
    expect(screen.queryByText('Tamil-label')).toBeNull()
  })

  it('the SPM grades page names its subjects in the words on screen (English), not Malay', () => {
    render(<GradesInputPage />)
    expect(screen.getAllByText('History').length).toBeGreaterThan(0)
    expect(screen.queryByText('Sejarah')).toBeNull()
  })

  it('the STPM grades page offers its subjects in English, not Malay or Tamil', () => {
    localStorage.setItem(KEY_STPM_STREAM, 'science')
    render(<StpmGradesPage />)
    // The STPM subject dropdowns (the options that carry the STPM codes), not the SPM block below them.
    const stpmSelect = screen.getAllByText('Physics')[0].closest('select') as HTMLSelectElement
    const labels = Array.from(stpmSelect.options).map((o) => o.textContent)
    expect(labels).toContain('Physics')
    expect(labels).not.toContain('Fizik')
    expect(labels).not.toContain('இயற்பியல்')
  })
})
