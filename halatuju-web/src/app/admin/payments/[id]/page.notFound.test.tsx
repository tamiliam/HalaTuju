/**
 * @jest-environment jsdom
 *
 * A PAYMENT RUN THAT IS NOT THERE — the screen this sprint was raised for.
 *
 * `/admin/payments/999999` MATCHES a route, so the address is a 200 and the page mounts. The GET
 * then failed, `.catch(() => setError(…))` ran — and `if (!run) return <Loading/>` sat ABOVE the
 * only place `error` is drawn, so the message was set and never reached. The page span on
 * "Loading…" for ever: no error, no empty state, no way out but the browser's Back button.
 *
 * ⚠ ASSERTING THE MESSAGE IS NOT ENOUGH. The broken page set the message too. What proves it is
 * the ABSENCE of the loading line, which is why both halves are in one test.
 */
import { render, screen, waitFor } from '@testing-library/react'

import PaymentRunPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin', is_super_admin: true, owning_org_id: 11 } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  useParams: () => ({ id: '999999' }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

/** How a run that is gone — or one the organisation fence refuses to admit exists — arrives. */
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
  mockApi.getPaymentRun.mockRejectedValue(gone())
  render(<PaymentRunPage />)
  // The first paint is honest: nothing has answered yet.
  expect(screen.getByText('common.loading')).toBeTruthy()
  await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
  expect(screen.queryByText('common.loading')).toBeNull()
})

it('keeps loading while the run has genuinely not answered', async () => {
  // The other direction, so the fix cannot be "always say not found". A pending promise must
  // read as pending — a run that is simply slow is not a run that is missing.
  mockApi.getPaymentRun.mockReturnValue(new Promise(() => {}))
  render(<PaymentRunPage />)
  await waitFor(() => expect(screen.getByText('common.loading')).toBeTruthy())
  expect(screen.queryByTestId('record-not-found')).toBeNull()
})
