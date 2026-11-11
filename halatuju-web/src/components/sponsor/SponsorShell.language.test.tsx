/**
 * @jest-environment jsdom
 *
 * TD-469 (owner D10, option A, 2026-11-11): the sponsor portal's desktop top row carries the language
 * select, the same `LanguageSelector` the student desktop row shows. On a phone it stays in My Account.
 */
import { render, fireEvent, within } from '@testing-library/react'
import SponsorShell from './SponsorShell'

const mockSetLocale = jest.fn(() => Promise.resolve())
jest.mock('next/navigation', () => ({ usePathname: () => '/sponsor/students', useRouter: () => ({ replace: jest.fn() }) }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href, prefetch: _p, ...rest }: { children: React.ReactNode; href: string; prefetch?: boolean }) =>
    <a href={href} {...rest}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en', setLocale: mockSetLocale }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'தமிழ்' },
}))
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => <span>logo</span> }))
jest.mock('@/components/ThemeSelector', () => ({ __esModule: true, default: () => <select aria-label="theme" /> }))
jest.mock('@/lib/sponsor-supabase', () => ({ sponsorSignOut: jest.fn() }))

beforeEach(() => jest.clearAllMocks())

/** The desktop row: `hidden md:flex`, shown from `md` up. */
const desktopRow = (c: HTMLElement) => c.querySelector('header div.hidden.md\\:flex') as HTMLElement

it.each([true, false])('the desktop row has the language select beside the theme (tabs: %s)', (nav) => {
  const { container } = render(<SponsorShell nav={nav}><p>page</p></SponsorShell>)
  const row = desktopRow(container)
  expect(row).not.toBeNull()
  const lang = within(row).getByRole('combobox', { name: 'Language' })
  expect(within(row).getByRole('combobox', { name: 'theme' })).toBeTruthy()
  // Exactly one language control in the header (none added to the phone header).
  expect(container.querySelectorAll('header select[aria-label="Language"]')).toHaveLength(1)
  expect((lang as HTMLSelectElement).value).toBe('en')
})

it('choosing a language there changes the locale', () => {
  const { container } = render(<SponsorShell nav><p>page</p></SponsorShell>)
  fireEvent.change(within(desktopRow(container)).getByRole('combobox', { name: 'Language' }), { target: { value: 'ta' } })
  expect(mockSetLocale).toHaveBeenCalledWith('ta')
})
