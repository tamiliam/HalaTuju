/**
 * @jest-environment jsdom
 *
 * The legacy pool route (A4.6 review): a ref goes on to its student page; an all-digit segment is a
 * pre-TD-074 raw-id link from an email already sent, and goes to the student LIST, never to a
 * "not available" page.
 */
import { render, waitFor } from '@testing-library/react'
import SponsorPoolDetailRedirect from './page'

let routeId = 'S-ABC123'
const mockReplace = jest.fn()
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: routeId }),
  useRouter: () => ({ replace: mockReplace }),
}))

beforeEach(() => { jest.clearAllMocks(); routeId = 'S-ABC123' })

it('passes a ref through to its student page', async () => {
  render(<SponsorPoolDetailRedirect />)
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/sponsor/students/S-ABC123'))
})

it('sends an old raw-id link to the student list', async () => {
  routeId = '4521'
  render(<SponsorPoolDetailRedirect />)
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/sponsor/students'))
  expect(mockReplace).not.toHaveBeenCalledWith('/sponsor/students/4521')
})
