/**
 * @jest-environment jsdom
 *
 * A SPONSOR RECORD THAT IS NOT THERE.
 *
 * This screen already told the officer SOMETHING on a failed load — a bare red line reading
 * `admin.sponsors.detail.loadFailed`. Two things were still wrong with it and both are pinned
 * here: the sentence claimed a load failure when a 404 is also a record the organisation fence
 * refuses to admit exists, and every detail screen said it differently (or, on two of them, not
 * at all). One shared state, one wording, proved by the same test on every screen.
 */
import { render, screen, waitFor } from '@testing-library/react'

import AdminSponsorDetailPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('next/navigation', () => ({ useParams: () => ({ id: '999999' }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin' } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const gone = () => {
  const err = new Error('Not found') as Error & { status?: number; code?: string }
  err.status = 404
  err.code = 'not_found'
  return err
}

beforeEach(() => {
  jest.clearAllMocks()
})

it('draws the not-found state and STOPS loading', async () => {
  mockApi.getSponsorDetail.mockRejectedValue(gone())
  render(<AdminSponsorDetailPage />)
  await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
  expect(screen.queryByText('common.loading')).toBeNull()
})

it('keeps loading while the record has genuinely not answered', async () => {
  mockApi.getSponsorDetail.mockReturnValue(new Promise(() => {}))
  render(<AdminSponsorDetailPage />)
  await waitFor(() => expect(screen.getByText('common.loading')).toBeTruthy())
  expect(screen.queryByTestId('record-not-found')).toBeNull()
})
