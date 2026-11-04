/**
 * @jest-environment jsdom
 *
 * Organisation → Programmes, the page (T5c P5): it draws the landing — fetched as its own chunk — for every
 * partner-login role, and declines in one line for a caller the menu would not show it to.
 */
import { render, screen } from '@testing-library/react'

import ProgrammesPage from './page'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
let mockRole: Record<string, unknown> | null = null
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/components/admin/ProgrammesLanding', () => ({
  __esModule: true, default: () => <div data-testid="landing">landing</div>,
}))

it('draws nothing before the role is known', () => {
  mockRole = null
  const { container } = render(<ProgrammesPage />)
  expect(container.textContent).toBe('')
})

it.each(['reviewer', 'mentor', 'org_admin', 'finance', 'qc'])('loads the landing for a %s', async (role) => {
  mockRole = { role, permissions: [] }
  render(<ProgrammesPage />)
  expect(await screen.findByTestId('landing')).toBeTruthy()
  expect(screen.queryByText('admin.programmes.landing.noAccess')).toBeNull()
})

it('declines for a source user, whose menu has no Programmes row', () => {
  mockRole = { role: 'source_partner', permissions: [] }
  render(<ProgrammesPage />)
  expect(screen.getByText('admin.programmes.landing.noAccess')).toBeTruthy()
  expect(screen.queryByTestId('landing')).toBeNull()
})
