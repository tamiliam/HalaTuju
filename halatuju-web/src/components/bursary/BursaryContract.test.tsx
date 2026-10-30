/**
 * @jest-environment jsdom
 *
 * Her contract on My Bursary (student maintenance S5b). Pinned:
 *  * "No contract on file" unless the server sends a platform-signed agreement;
 *  * the Overview card is compact (date + View PDF), the tab lists the parties;
 *  * "View PDF" asks for a link ONLY on the click (`link: true`), opens it in a tab opened on the click
 *    itself, and a click that brings no link closes that tab, says so and can be tried again.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import BursaryContract from './BursaryContract'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const SIGNED = (pdf: string | null, witnessed = false): api.BursaryContract => ({
  exists: true, executed_on: '2026-08-03', witnessed, pdf_url: pdf, pdf_expires_in: 300,
  parties: [{ role: 'student', name: 'NUR AISYAH', signed_on: '2026-08-01' },
    { role: 'guarantor', name: 'SITI', relationship: 'mother', signed_on: '2026-08-01' },
    { role: 'foundation', name: 'DR KUMAR', title: 'Chair', signed_on: '2026-08-03' }],
})

let fakeTab: { opener: unknown; location: { href: string }; close: jest.Mock }
beforeEach(() => {
  jest.clearAllMocks()
  fakeTab = { opener: 'x', location: { href: '' }, close: jest.fn() }
  jest.spyOn(window, 'open').mockReturnValue(fakeTab as unknown as Window)
})

it('says No contract on file when there is none', () => {
  render(<BursaryContract contract={{ exists: false }} token="tok" />)
  expect(screen.getByTestId('contract-none').textContent).toBe('bursaryTabs.contract.none')
  expect(screen.queryByText('bursaryTabs.contract.viewPdf')).toBeNull()
})

it('the compact card shows the date and View PDF, not the parties', () => {
  render(<BursaryContract contract={SIGNED(null)} token="tok" compact />)
  expect(screen.getByTestId('contract-signed').textContent).toContain('bursaryTabs.contract.countersigned')
  expect(screen.queryByTestId('contract-parties')).toBeNull()
  expect(mockApi.getBursaryContract).not.toHaveBeenCalled()             // no link until she asks
})

it('opens a fresh link on the click; a click with no link closes the tab and can be retried', async () => {
  mockApi.getBursaryContract
    .mockResolvedValueOnce(SIGNED(null, true))
    .mockResolvedValueOnce(SIGNED('https://signed/pdf', true))
  render(<BursaryContract contract={SIGNED(null, true)} token="tok" />)
  expect(screen.getByTestId('contract-parties').textContent).toContain('SITI')
  expect(screen.getByTestId('contract-signed').textContent).toContain('bursaryTabs.contract.signed')
  fireEvent.click(screen.getByText('bursaryTabs.contract.viewPdf'))
  expect(await screen.findByTestId('contract-no-pdf')).toBeTruthy()
  expect(fakeTab.close).toHaveBeenCalled()
  expect(mockApi.getBursaryContract).toHaveBeenLastCalledWith({ token: 'tok', link: true })
  fireEvent.click(screen.getByText('bursaryTabs.contract.viewPdf'))
  await waitFor(() => expect(fakeTab.location.href).toBe('https://signed/pdf'))
  expect(fakeTab.opener).toBeNull()
  expect(screen.queryByTestId('contract-no-pdf')).toBeNull()
})
