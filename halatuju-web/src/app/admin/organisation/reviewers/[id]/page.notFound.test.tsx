/**
 * @jest-environment jsdom
 *
 * A REVIEWER RECORD THAT IS NOT THERE. Same claim as the other four detail screens, on the
 * screen that had its own third wording for it (`admin.reviewers.detail.loadFailed`).
 */
import { render, screen, waitFor } from '@testing-library/react'

import AdminReviewerDetailPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('next/navigation', () => ({ useParams: () => ({ id: '999999' }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
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
  mockApi.getReviewerDetail.mockRejectedValue(gone())
  render(<AdminReviewerDetailPage />)
  await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
  expect(screen.queryByText('common.loading')).toBeNull()
})

it('keeps loading while the record has genuinely not answered', async () => {
  mockApi.getReviewerDetail.mockReturnValue(new Promise(() => {}))
  render(<AdminReviewerDetailPage />)
  await waitFor(() => expect(screen.getByText('common.loading')).toBeTruthy())
  expect(screen.queryByTestId('record-not-found')).toBeNull()
})
