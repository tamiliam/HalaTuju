/**
 * @jest-environment jsdom
 *
 * The scholar file's Contract tab (student maintenance S5a). Pinned:
 *  * "No contract on file" unless the server sends an EXECUTED agreement (platform-signed only);
 *  * an executed one shows its date and the parties;
 *  * "View signed PDF" asks the server for a FRESH link (it lives five minutes) and opens it in the
 *    viewer — never the link fetched when the tab first opened.
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

const EXECUTED = (url: string): api.ScholarContract => ({
  exists: true, executed_on: '2026-07-01', version: '2026-v1', pdf_url: url, pdf_expires_in: 300,
  parties: [{ role: 'student', name: 'NUR AISYAH', signed_on: '2026-06-20' },
    { role: 'guarantor', name: 'SITI', relationship: 'mother', signed_on: '2026-06-20' },
    { role: 'foundation', name: 'DR KUMAR', title: 'Chair', signed_on: '2026-06-30' },
    { role: 'witness', name: 'MS LEE', organisation: 'Partner', signed_on: '2026-07-01' }],
})

beforeEach(() => jest.clearAllMocks())

it('says No contract on file when nothing executed is on file', async () => {
  mockApi.getScholarContract.mockResolvedValue({ exists: false })
  render(<ScholarContract id={7} token="tok" />)
  expect(await screen.findByTestId('contract-none')).toBeTruthy()
  expect(screen.queryByText('admin.scholars.contractTab.viewPdf')).toBeNull()
})

it('shows the executed date and the parties, and opens a FRESH link', async () => {
  mockApi.getScholarContract
    .mockResolvedValueOnce(EXECUTED('https://signed/first'))
    .mockResolvedValueOnce(EXECUTED('https://signed/fresh'))
  render(<ScholarContract id={7} token="tok" />)
  expect((await screen.findByTestId('contract-executed')).textContent).toContain('admin.scholars.contractTab.executedOn')
  expect(screen.getByTestId('contract-parties').textContent).toContain('SITI')
  fireEvent.click(screen.getByText('admin.scholars.contractTab.viewPdf'))
  await waitFor(() => expect(mockViewer).toHaveBeenLastCalledWith(expect.objectContaining({
    url: 'https://signed/fresh', kind: 'pdf' })))
  expect(mockApi.getScholarContract).toHaveBeenCalledTimes(2)
})
