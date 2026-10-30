/**
 * @jest-environment jsdom
 *
 * One student as a source sees them, and the witness step (source sign-in S3 + S4).
 *
 * Pinned: a LISTED application shows Profile (with phone and email — owner ruling) and Application
 * (stage with the told date, the missing PART names in plain words); a WITNESS-ONLY case shows the
 * name, the gift and the contract and nothing else (C14); "Review and witness" appears only when the
 * server's `can_witness` says so. The witness form stays dead until a name AND the tick are given;
 * the PDF link is asked for on a click, never on load; every refusal code has its own words; after
 * signing the page shows the signed state and nothing to press. The witness step lives IN the
 * student's page (`?step=witness`): opened in place, on arrival from a link, and Back re-reads.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SourceStudent from './SourceStudent'
import SourceWitness from './SourceWitness'
import * as api from '@/lib/admin-api'
import { AGREEMENT, LISTED, LISTED_MISSING, WITNESS_ONLY } from './testFixtures'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}|${Object.values(v).join(',')}` : k),
                 locale: 'en' }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'source_partner', source_name: 'MUETMyWay',
                                               admin_name: 'Audrey Koh Sui Ean' } }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => { jest.clearAllMocks() })

describe('SourceStudent', () => {
  it('a listed student: Profile, Application with the told date, and the contract waiting for you', async () => {
    mockApi.getSourceApplication.mockResolvedValue(LISTED)
    render(<SourceStudent id="104" />)
    const profile = await screen.findByTestId('student-profile')
    for (const v of ['SMK Taman Melawati', 'Selangor', 'admin.sourceConsole.level.stpm', '012-345 6789',
      'harish.k@example.com']) expect(profile.textContent).toContain(v)
    const app = screen.getByTestId('student-application')
    expect(app.textContent).toContain('Harapan Bursary')
    expect(app.textContent).toContain('admin.sourceConsole.student.toldOn|admin.sourceConsole.stage.awarded,')
    expect(app.textContent).toContain('admin.sourceConsole.student.none')
    expect(screen.getByText('admin.sourceConsole.student.footnote')).toBeTruthy()
    expect(mockApi.getSourceApplication).toHaveBeenCalledWith('104', { token: 'tok' })
  })

  it('"Review and witness" opens the witness step in place; Back returns and re-reads', async () => {
    mockApi.getSourceApplication.mockResolvedValue(LISTED)
    mockApi.getSourceAgreement.mockResolvedValue(AGREEMENT)
    render(<SourceStudent id="104" />)
    fireEvent.click(await screen.findByText('admin.sourceConsole.contract.review'))
    expect(await screen.findByTestId('witness-panel')).toBeTruthy()
    expect(window.location.search).toBe('?step=witness')
    fireEvent.click(screen.getByText(/admin\.sourceConsole\.witness\.back/))
    expect(await screen.findByTestId('student-profile')).toBeTruthy()
    expect(window.location.search).toBe('')
    expect(mockApi.getSourceApplication).toHaveBeenCalledTimes(2)
  })

  it('arriving with ?step=witness (the Overview\'s link) opens the step at once', async () => {
    mockApi.getSourceApplication.mockResolvedValue(LISTED)
    mockApi.getSourceAgreement.mockResolvedValue(AGREEMENT)
    window.history.replaceState(null, '', '/admin/scholarship/104?step=witness')
    try {
      render(<SourceStudent id="104" />)
      expect(await screen.findByTestId('witness-panel')).toBeTruthy()
      expect(mockApi.getSourceAgreement).toHaveBeenCalledWith('104', { token: 'tok' })
    } finally { window.history.replaceState(null, '', '/') }
  })

  it('names the missing parts in plain words, and says when there is no contract yet', async () => {
    mockApi.getSourceApplication.mockResolvedValue(LISTED_MISSING)
    render(<SourceStudent id="101" />)
    const app = await screen.findByTestId('student-application')
    expect(app.textContent).toContain('admin.sourceConsole.part.documents, admin.sourceConsole.part.guardian_documents')
    expect(screen.getByTestId('source-contract').textContent).toContain('admin.sourceConsole.contract.none')
    expect(screen.queryByText('admin.sourceConsole.contract.review')).toBeNull()
  })

  it('a witness-only case: the name, the gift and the contract — no profile, no stage', async () => {
    mockApi.getSourceApplication.mockResolvedValue(WITNESS_ONLY)
    render(<SourceStudent id="207" />)
    await screen.findByText('admin.sourceConsole.student.witnessOnly')
    expect(screen.getByText('Kavin Selvam')).toBeTruthy()
    expect(screen.queryByTestId('student-profile')).toBeNull()
    expect(screen.queryByText(/admin\.sourceConsole\.stage\./)).toBeNull()
    expect(screen.getByText('admin.sourceConsole.contract.review')).toBeTruthy()
  })

  it('out of scope is the neutral not-found state', async () => {
    mockApi.getSourceApplication.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    render(<SourceStudent id="9" />)
    expect(await screen.findByTestId('record-not-found')).toBeTruthy()
  })
})

describe('SourceWitness', () => {
  const sign = () => screen.getByText('admin.sourceConsole.witness.sign').closest('button') as HTMLButtonElement
  const open = async () => {
    mockApi.getSourceAgreement.mockResolvedValue(AGREEMENT)
    render(<SourceWitness id="104" onBack={() => {}} />)
    await screen.findByTestId('witness-panel')
  }

  it('starts with the user\'s own name, and stays dead until the box is ticked and a name given', async () => {
    await open()
    expect(screen.getByDisplayValue('Audrey Koh Sui Ean')).toBeTruthy()
    expect(sign().disabled).toBe(true)
    fireEvent.click(screen.getByRole('checkbox'))
    expect(sign().disabled).toBe(false)
    fireEvent.change(screen.getByDisplayValue('Audrey Koh Sui Ean'), { target: { value: '   ' } })
    expect(sign().disabled).toBe(true)
    expect(screen.getByText('admin.sourceConsole.witness.intro|MUETMyWay')).toBeTruthy()
    expect(screen.getByText('admin.sourceConsole.witness.confirm|MUETMyWay')).toBeTruthy()
  })

  it('asks for the PDF link only when the button is pressed', async () => {
    await open()
    expect(mockApi.getSourceAgreement).toHaveBeenCalledTimes(1)
    expect(mockApi.getSourceAgreement).toHaveBeenCalledWith('104', { token: 'tok' })
    mockApi.getSourceAgreement.mockResolvedValueOnce({ ...AGREEMENT, pdf_url: 'https://files.example/a.pdf' })
    fireEvent.click(screen.getByText('admin.sourceConsole.witness.openPdf'))
    await waitFor(() => expect(mockApi.getSourceAgreement).toHaveBeenLastCalledWith('104', { token: 'tok', link: true }))
    await waitFor(() => expect(document.querySelector('iframe')?.getAttribute('src')).toContain('a.pdf'))
  })

  it('says so when no PDF comes back', async () => {
    await open()
    mockApi.getSourceAgreement.mockResolvedValueOnce(AGREEMENT)
    fireEvent.click(screen.getByText('admin.sourceConsole.witness.openPdf'))
    expect(await screen.findByTestId('witness-no-pdf')).toBeTruthy()
  })

  it('signs with the typed name and the tick, then shows the signed state', async () => {
    mockApi.witnessAsSource.mockResolvedValue({ ...AGREEMENT, witness_signed_at: '2026-10-30T03:00:00Z',
                                                can_witness: false })
    await open()
    fireEvent.change(screen.getByDisplayValue('Audrey Koh Sui Ean'), { target: { value: ' Audrey Koh ' } })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(sign())
    await waitFor(() => expect(mockApi.witnessAsSource).toHaveBeenCalledWith(
      '104', { witness_name: 'Audrey Koh', confirm: true }, { token: 'tok' }))
    expect((await screen.findByTestId('witness-done')).textContent).toContain('admin.sourceConsole.witness.done')
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  it.each(['not_ready', 'contract_not_live', 'confirm_required', 'name_required', 'name_too_long',
    'not_found', 'source_unavailable'])('shows the %s refusal in its own words', async (code) => {
    mockApi.witnessAsSource.mockRejectedValue(Object.assign(new Error(code), { code }))
    await open()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(sign())
    await waitFor(() => expect(screen.getByRole('alert').textContent)
      .toBe(`admin.sourceConsole.witness.error.${code}`))
  })

  it('already witnessed elsewhere: says so and reloads to the signed state', async () => {
    mockApi.witnessAsSource.mockRejectedValue(Object.assign(new Error('x'), { code: 'already_witnessed' }))
    await open()
    mockApi.getSourceAgreement.mockResolvedValueOnce({ ...AGREEMENT, witness_signed_at: '2026-10-30T03:00:00Z',
                                                       can_witness: false })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(sign())
    expect(await screen.findByTestId('witness-done')).toBeTruthy()
  })

  it('an unknown refusal reads in generic words', async () => {
    mockApi.witnessAsSource.mockRejectedValue(Object.assign(new Error('x'), { code: 'odd' }))
    await open()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(sign())
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('admin.sourceConsole.witness.error.generic'))
  })

  it('a contract no longer open for a witness offers nothing to press', async () => {
    mockApi.getSourceAgreement.mockResolvedValue({ ...AGREEMENT, can_witness: false })
    render(<SourceWitness id="104" onBack={() => {}} />)
    expect(await screen.findByTestId('witness-closed')).toBeTruthy()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  it('not this source\'s contract (404) is the neutral not-found state', async () => {
    mockApi.getSourceAgreement.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    render(<SourceWitness id="5" onBack={() => {}} />)
    expect(await screen.findByTestId('record-not-found')).toBeTruthy()
  })
})
