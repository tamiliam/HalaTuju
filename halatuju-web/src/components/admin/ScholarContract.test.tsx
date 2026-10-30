/**
 * @jest-environment jsdom
 *
 * The scholar file's Contract tab (student maintenance S5a). Pinned:
 *  * "No contract on file" unless the server sends a platform-signed (countersigned) agreement;
 *  * the line uses the Overview card's words — "Countersigned by the organisation" until the
 *    (non-blocking) witness signs, then "Signed and executed" (review H1);
 *  * the FIRST read asks for no link; "View signed PDF" asks for a fresh one (`link: true`) each time;
 *  * a click that comes back without a link says so and leaves the button working (review L6), and a
 *    later success clears any earlier failure.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarContract from './ScholarContract'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
const mockViewer = jest.fn()
jest.mock('@/components/DocViewer', () => ({
  __esModule: true,
  default: (props: { doc: unknown }) => { mockViewer(props.doc); return null },
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const SIGNED = (url: string | null, witnessed = true): api.ScholarContract => ({
  exists: true, executed_on: '2026-07-01', witnessed, version: '2026-v1', pdf_url: url, pdf_expires_in: 300,
  parties: [{ role: 'student', name: 'NUR AISYAH', signed_on: '2026-06-20' },
    { role: 'guarantor', name: 'SITI', relationship: 'mother', signed_on: '2026-06-20' },
    { role: 'foundation', name: 'DR KUMAR', title: 'Chair', signed_on: '2026-06-30' }],
})

beforeEach(() => jest.clearAllMocks())

it('says No contract on file when nothing platform-signed is on file', async () => {
  mockApi.getScholarContract.mockResolvedValue({ exists: false })
  render(<ScholarContract id={7} token="tok" />)
  expect(await screen.findByTestId('contract-none')).toBeTruthy()
  expect(screen.queryByText('admin.scholars.contractTab.viewPdf')).toBeNull()
})

it('a countersigned agreement uses the card’s words, and the first read asks for no link', async () => {
  mockApi.getScholarContract.mockResolvedValue(SIGNED(null, false))
  render(<ScholarContract id={7} token="tok" />)
  expect((await screen.findByTestId('contract-executed')).textContent).toContain('admin.scholars.contractTab.countersignedOn')
  expect(mockApi.getScholarContract).toHaveBeenCalledWith(7, { token: 'tok' })
  const button = screen.getByText('admin.scholars.contractTab.viewPdf').closest('button')!
  expect(button.disabled).toBe(false)                          // no link yet, and still clickable
})

it('opens a FRESH link on click; a click with no link says so and can be tried again', async () => {
  mockApi.getScholarContract
    .mockResolvedValueOnce(SIGNED(null))                       // the first read: no link
    .mockResolvedValueOnce(SIGNED(null))                       // a click: storage refused
    .mockResolvedValueOnce(SIGNED('https://signed/fresh'))     // a retry
  render(<ScholarContract id={7} token="tok" />)
  expect((await screen.findByTestId('contract-executed')).textContent).toContain('admin.scholars.contractTab.executedOn')
  fireEvent.click(screen.getByText('admin.scholars.contractTab.viewPdf'))
  expect(await screen.findByTestId('contract-no-pdf')).toBeTruthy()
  expect(mockApi.getScholarContract).toHaveBeenLastCalledWith(7, { token: 'tok', link: true })
  fireEvent.click(screen.getByText('admin.scholars.contractTab.viewPdf'))
  await waitFor(() => expect(mockViewer).toHaveBeenLastCalledWith(expect.objectContaining({
    url: 'https://signed/fresh', kind: 'pdf' })))
  expect(screen.queryByTestId('contract-no-pdf')).toBeNull()
})

it('a failed first read clears once a later read succeeds', async () => {
  mockApi.getScholarContract
    .mockResolvedValueOnce(SIGNED(null))
    .mockRejectedValueOnce(new Error('x'))
    .mockResolvedValueOnce(SIGNED('https://signed/ok'))
  render(<ScholarContract id={7} token="tok" />)
  await screen.findByTestId('contract-executed')
  fireEvent.click(screen.getByText('admin.scholars.contractTab.viewPdf'))
  expect(await screen.findByText('admin.scholars.contractTab.loadFailed')).toBeTruthy()
  fireEvent.click(screen.getByText('admin.scholars.contractTab.viewPdf'))
  await waitFor(() => expect(screen.queryByText('admin.scholars.contractTab.loadFailed')).toBeNull())
})
