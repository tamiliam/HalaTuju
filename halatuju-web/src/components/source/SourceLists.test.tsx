/**
 * @jest-environment jsdom
 *
 * The source console's Overview, Applications and Scholars (source sign-in S3 + S4), each drawn
 * from a fixture of the exact backend JSON (`testFixtures.ts`).
 *
 * Pinned: the crumb's gift travels as `p`; every stage is a tile, so the tiles add up to the total;
 * the witness banner and the chase list; the Applications search (by name) and stage filter (the
 * server's keys); "Your witness needed" comes from the Overview's `witness_waiting`, never from a
 * guess at the contract stage; and no money, scores or results are drawn anywhere.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SourceOverview from './SourceOverview'
import SourceApplications from './SourceApplications'
import SourceScholars from './SourceScholars'
import SourceScholar from './SourceScholar'
import * as api from '@/lib/admin-api'
import { APPLICATIONS, OVERVIEW, SCHOLAR, SCHOLARS } from './testFixtures'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}|${Object.values(v).join(',')}` : k),
                 locale: 'en' }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'source_partner', source_name: 'MUETMyWay' } }),
}))
jest.mock('@/lib/admin-api')
jest.mock('@/lib/useGiftInUrl', () => ({ useGiftInUrl: () => true }))
let mockGift: string | undefined = 'flag'
jest.mock('@/lib/programmeScope', () => ({ useProgrammeParam: () => mockGift }))
const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  jest.clearAllMocks()
  mockGift = 'flag'
  mockApi.getSourceOverview.mockResolvedValue(OVERVIEW)
  mockApi.getSourceApplications.mockResolvedValue(APPLICATIONS)
  mockApi.getSourceScholars.mockResolvedValue(SCHOLARS)
  mockApi.getSourceScholar.mockResolvedValue(SCHOLAR)
})

describe('SourceOverview', () => {
  it('draws every stage as a tile, the scholars and the total, for the crumb\'s gift', async () => {
    render(<SourceOverview />)
    await waitFor(() => expect(screen.getByTestId('stage-tiles')).toBeTruthy())
    expect(mockApi.getSourceOverview).toHaveBeenCalledWith('flag', { token: 'tok' })
    expect(screen.getByText('admin.sourceConsole.overview.subtitleFor|MUETMyWay,Harapan Bursary')).toBeTruthy()
    expect(screen.getByTestId('tile-under_review').textContent).toBe('admin.sourceConsole.stage.under_review21')
    expect(screen.getByTestId('tile-closed').textContent).toBe('admin.sourceConsole.stage.closed1')
    expect(screen.getByTestId('tile-scholars').textContent).toBe('admin.sourceConsole.overview.scholars3')
    expect(screen.getByTestId('overview-total').textContent).toBe('admin.sourceConsole.overview.total|45')
    expect(screen.getByText('admin.sourceConsole.overview.toldFootnote')).toBeTruthy()
  })

  it('asks the contract waiting for this source to be witnessed, linking to the witness step', async () => {
    render(<SourceOverview />)
    const banner = await screen.findByTestId('witness-banner')
    expect(banner.textContent).toContain('admin.sourceConsole.overview.witnessOne')
    const now = screen.getByText('admin.sourceConsole.overview.witnessNow').closest('a') as HTMLAnchorElement
    expect(now.getAttribute('href')).toBe('/admin/scholarship/104?step=witness')
  })

  it('lists the chase list with dates and an Open link — and no banner when nothing waits', async () => {
    mockApi.getSourceOverview.mockResolvedValue({ ...OVERVIEW, witness_waiting: [] })
    render(<SourceOverview />)
    const list = await screen.findByTestId('missing-items')
    expect(list.textContent).toContain('Priya Devi')
    expect(list.querySelector('a')?.getAttribute('href')).toBe('/admin/scholarship/101')
    expect(screen.queryByTestId('witness-banner')).toBeNull()
  })

  it('with no gift chosen, asks for every gift and says so neutrally', async () => {
    mockGift = undefined
    mockApi.getSourceOverview.mockResolvedValue({ ...OVERVIEW, programme: null })
    render(<SourceOverview />)
    await screen.findByText('admin.sourceConsole.overview.subtitle|MUETMyWay')
    expect(mockApi.getSourceOverview).toHaveBeenCalledWith(undefined, { token: 'tok' })
  })
})

describe('SourceApplications', () => {
  it('lists Student, School, Level, Sent and Stage — the name linking to the student', async () => {
    render(<SourceApplications />)
    const link = (await screen.findByText('Priya Devi')).closest('a') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/admin/scholarship/101')
    expect(screen.getByText('SMK Seri Garing')).toBeTruthy()
    expect(screen.getAllByText('admin.sourceConsole.level.spm').length).toBe(1)
    expect(screen.getAllByText('admin.sourceConsole.stage.shortlisted').length).toBeGreaterThan(0)
    expect(screen.getByText('admin.sourceConsole.applications.footnote')).toBeTruthy()
    expect(mockApi.getSourceApplications).toHaveBeenCalledWith(
      { p: 'flag', q: '', stage: '', page: 1, page_size: 25 }, { token: 'tok' })
  })

  it('searches by name and filters by the server\'s stage keys', async () => {
    render(<SourceApplications />)
    await screen.findByText('Priya Devi')
    fireEvent.change(screen.getByLabelText('admin.sourceConsole.applications.search'), { target: { value: 'Priya' } })
    await waitFor(() => expect(mockApi.getSourceApplications).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: 'Priya' }), { token: 'tok' }))
    fireEvent.change(screen.getByLabelText('admin.sourceConsole.applications.stageFilter'),
      { target: { value: 'under_review' } })
    await waitFor(() => expect(mockApi.getSourceApplications).toHaveBeenLastCalledWith(
      expect.objectContaining({ stage: 'under_review', page: 1 }), { token: 'tok' }))
    const stageBox = screen.getByLabelText('admin.sourceConsole.applications.stageFilter')
    const options = Array.from(stageBox.querySelectorAll('option')).map((o) => o.getAttribute('value'))
    expect(options).toEqual(['', 'not_shortlisted', 'shortlisted', 'awaiting_review', 'under_review',
      'awarded', 'rejected', 'closed'])
  })
})

describe('SourceScholars', () => {
  it('lists scholar, institution, course, status and contract — "Your witness needed" from the Overview', async () => {
    render(<SourceScholars />)
    await screen.findByText('Janani Muthu')
    const needed = screen.getByText('admin.sourceConsole.scholars.witnessNeeded').closest('a') as HTMLAnchorElement
    expect(needed.getAttribute('href')).toBe('/admin/scholarship/104?step=witness')
    expect(screen.getByText('admin.scholars.contract.executed')).toBeTruthy()
    expect(screen.getByText('admin.scholarship.statuses.active')).toBeTruthy()
    expect(mockApi.getSourceScholars).toHaveBeenCalledWith({ p: 'flag', page: 1, page_size: 25 }, { token: 'tok' })
    expect(screen.getByText('admin.sourceConsole.scholars.footnote')).toBeTruthy()
  })

  it('reads the contract stage when nothing waits for this source', async () => {
    mockApi.getSourceOverview.mockResolvedValue({ ...OVERVIEW, witness_waiting: [] })
    render(<SourceScholars />)
    await screen.findByText('Harish A/L Kumar')
    await waitFor(() => expect(screen.getByText('admin.scholars.contract.binds')).toBeTruthy())
    expect(screen.queryByText('admin.sourceConsole.scholars.witnessNeeded')).toBeNull()
  })
})

describe('SourceScholar', () => {
  it('adds phone, email and the contract — and nothing about money', async () => {
    render(<SourceScholar id="105" />)
    const details = await screen.findByTestId('scholar-details')
    expect(details.textContent).toContain('011-222 3333')
    expect(details.textContent).toContain('janani@example.com')
    expect(details.textContent).toContain('Politeknik Ungku Omar')
    expect(screen.getByTestId('source-contract').textContent).toContain('admin.sourceConsole.contract.youWitnessed')
    expect(document.body.textContent).not.toMatch(/RM|admin\.scholars\.money/)
  })

  it('a scholar the server will not show is the neutral not-found state', async () => {
    mockApi.getSourceScholar.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    render(<SourceScholar id="999" />)
    await waitFor(() => expect(screen.queryByTestId('source-scholar')).toBeNull())
    await waitFor(() => expect(document.body.textContent).toContain('errors.recordNotFound'))
  })
})
