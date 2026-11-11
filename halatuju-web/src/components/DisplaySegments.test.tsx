/**
 * @jest-environment jsdom
 *
 * Owner 2026-11-12 (A48): the menu's language row shows Malay SHORT ("B. Melayu") so it stays on one
 * line, while the button's accessible name stays the full "Bahasa Melayu".
 */
import { render, screen } from '@testing-library/react'
import { LanguageSegments } from './DisplaySegments'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en', setLocale: jest.fn(() => Promise.resolve()) }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'தமிழ்' },
  LOCALE_SHORT_LABELS: { en: 'English', ms: 'B. Melayu', ta: 'தமிழ்' },
}))
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: jest.fn() }) }))

it('shows "B. Melayu" with the accessible name "Bahasa Melayu"', () => {
  render(<LanguageSegments />)
  const ms = screen.getByRole('radio', { name: 'Bahasa Melayu' })
  expect(ms.textContent).toBe('B. Melayu')
  expect(ms.className).toContain('whitespace-nowrap')
  expect(screen.queryByText('Bahasa Melayu')).toBeNull()
})
