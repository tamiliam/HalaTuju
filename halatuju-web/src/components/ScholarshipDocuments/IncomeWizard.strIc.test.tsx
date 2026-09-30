/**
 * @jest-environment jsdom
 *
 * TD-309 — THE DOCUMENTS PAGE OFFERS THE IC THAT SETTLES WHOSE STR IT IS.
 *
 * The owner's own example: the MOTHER's STR, with only the father's IC on file. Before TD-309 the
 * wizard gave a `parent_ic` card only to the STR earner or to ticked working members, so her IC had
 * nowhere to go until Check 2 asked for it after submission. The api now serves
 * `str_check.ic_slots` (the same rule Check 2 asks from) and the wizard draws one extra card per
 * named member — TAGGED to her, and NOT required (owner: option 1, the gate is unchanged).
 *
 * Harness copied from `../ScholarshipDocuments.test.tsx`: `t` echoes its key, so every assertion
 * reads an i18n key, never English copy.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarshipDocuments from '../ScholarshipDocuments'
import type { ApplicationRequirements, ScholarshipApplication } from '@/lib/api'
import { sandboxApplication } from '@/sandbox/fixtures/scholarship'
import * as api from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  listDocuments: jest.fn(),
  getConsentStatus: jest.fn(),
  signUploadDocument: jest.fn(),
  uploadFileToSignedUrl: jest.fn(),
  recordDocument: jest.fn(),
  deleteDocument: jest.fn(),
  updateScholarshipDetails: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
}))
// The per-file coach draws a marker naming its document, so a test can see WHICH card spoke
// (review F3). It fetches its own advice in the product; that is not what this file is about.
jest.mock('../DocumentHelpCoach', () => ({
  __esModule: true,
  default: ({ doc }: { doc: { id: number } }) => <p data-testid={`coach-${doc.id}`}>coach</p>,
}))
jest.mock('../IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const W = 'scholarship.docs.income.wizard'
const MOTHER_IC = `${W}.icTitle.mother`
const FATHER_IC = `${W}.icTitle.father`
// ONE member-neutral line (the card title already names her) — five per-member lines cost
// `/scholarship/apply` its budget line, which only ever sees en.json (TD-309 build).
const MOTHER_HELP = `${W}.strIcHelp`

const FULL: ApplicationRequirements = {
  documents: {
    required: ['ic', 'income_proof', 'offer_letter', 'results_slip'],
    optional: ['electricity_bill', 'photo', 'school_leaving_cert', 'statement_of_intent',
               'water_bill'],
  },
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getConsentStatus.mockResolvedValue(
    { is_minor: false, consents: [] } as unknown as api.ConsentStatus,
  )
  mockApi.signUploadDocument.mockResolvedValue(
    { upload_url: 'https://signed.example/u', storage_path: 'p/mother-ic.pdf' } as never)
  mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
  mockApi.recordDocument.mockResolvedValue({} as never)
})

const doc = (id: number, docType: string, member: string, extra: Record<string, unknown> = {}) => ({
  id, doc_type: docType, household_member: member,
  original_filename: `${docType}-${member || 'household'}.pdf`, content_type: 'application/pdf',
  size: 1234, verification_status: 'pending', download_url: 'https://example.test/d',
  uploaded_at: '2026-09-01T00:00:00Z', ...extra,
}) as unknown as api.ApplicantDocument

/** The mother's STR: it names her, the father's IC does not match, her IC is not on file. */
const mothersStr = (missing: string[], unreadable: string[] = []) => doc(9, 'str', 'father', {
  str_check: {
    name: 'Kamala A/P Suppiah', nric: '750808-14-5002', status: 'Lulus', year: '2026',
    member: 'father', name_status: 'mismatch', nric_status: 'mismatch',
    current_status: 'current', ic_present: true, ic_slots: { missing, unreadable },
  },
})

const student = async (route: 'str' | 'salary', documents: api.ApplicantDocument[]) => {
  mockApi.listDocuments.mockResolvedValue({ documents })
  render(<ScholarshipDocuments token="sandbox-token" app={{
    ...sandboxApplication, requirements: FULL, income_route: route,
    income_earner: route === 'str' ? 'father' : '', income_working_members: ['father'],
  } as unknown as ScholarshipApplication} />)
  await waitFor(() => expect(screen.getByText('scholarship.docs.section.identity.title')).toBeTruthy())
}

/** The card a title sits in — the bordered box that also holds its file input. */
const cardOf = (titleKey: string): HTMLElement => {
  const card = screen.getByText(titleKey, { exact: false }).closest('.border.rounded-lg')
  if (!card) throw new Error(`no card around ${titleKey}`)
  return card as HTMLElement
}

describe('STR route — the mother\'s STR with only the father\'s IC', () => {
  it('offers a Mother\'s IC card with the STR help line, and no required star', async () => {
    await student('str', [doc(1, 'parent_ic', 'father'), mothersStr(['mother'])])
    const title = screen.getByText(MOTHER_IC, { exact: false })
    expect(title.textContent).toBe(MOTHER_IC)          // no " *" — offered, not demanded
    expect(screen.getByText(MOTHER_HELP)).toBeTruthy()
    // the control: the earner's own IC card IS required, so the star is what we think it is
    expect(screen.getByText(FATHER_IC, { exact: false }).textContent).toBe(`${FATHER_IC} *`)
  })

  it('an upload into it is TAGGED to the mother', async () => {
    await student('str', [doc(1, 'parent_ic', 'father'), mothersStr(['mother'])])
    const input = cardOf(MOTHER_IC).querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['x'], 'mother-ic.pdf', { type: 'application/pdf' })
    await act(async () => { fireEvent.change(input, { target: { files: [file] } }) })
    await waitFor(() => expect(mockApi.recordDocument).toHaveBeenCalled())
    expect(mockApi.recordDocument.mock.calls[0][0]).toMatchObject(
      { doc_type: 'parent_ic', household_member: 'mother' })
  })

  it('the father\'s IC card is unchanged — one card, not two', async () => {
    // The STR's slots may name the earner too; the earner already owns a card.
    await student('str', [doc(1, 'parent_ic', 'father'), mothersStr(['father', 'mother'])])
    expect(screen.getAllByText(FATHER_IC, { exact: false })).toHaveLength(1)
    expect(screen.getAllByText(MOTHER_IC, { exact: false })).toHaveLength(1)
  })

  it('her IC on file but unread is offered too — the same card, holding her file', async () => {
    await student('str', [doc(1, 'parent_ic', 'father'), doc(2, 'parent_ic', 'mother'),
                          mothersStr([], ['mother'])])
    expect(screen.getByText(MOTHER_IC)).toBeTruthy()
    expect(screen.getByText('parent_ic-mother.pdf')).toBeTruthy()
  })

  it('both lists empty (the family\'s own STR) → no extra card', async () => {
    await student('str', [doc(1, 'parent_ic', 'father'), mothersStr([])])
    expect(screen.queryByText(MOTHER_IC, { exact: false })).toBeNull()
    expect(screen.queryByText(MOTHER_HELP)).toBeNull()
  })
})

describe('review F1 — the help line says WHY the card is there', () => {
  const MOTHER_IC_HELP = `${W}.icHelp.mother`

  it('a member kept only because her IC is on file reads the ordinary IC help, not the STR line', async () => {
    // Her IC has settled the STR (slots empty) — the card stays so her upload never vanishes,
    // but "a name we could not match" is no longer true.
    await student('str', [doc(1, 'parent_ic', 'father'), doc(2, 'parent_ic', 'mother'), mothersStr([])])
    expect(screen.getByText(MOTHER_IC)).toBeTruthy()
    expect(screen.getByText(MOTHER_IC_HELP)).toBeTruthy()
    expect(screen.queryByText(MOTHER_HELP)).toBeNull()
  })

  it('the SAME card switches from the STR line to the IC help once her IC lands and settles it', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [doc(1, 'parent_ic', 'father'), mothersStr(['mother'])] })
    const app = {
      ...sandboxApplication, requirements: FULL, income_route: 'str',
      income_earner: 'father', income_working_members: ['father'],
    } as unknown as ScholarshipApplication
    const view = render(<ScholarshipDocuments token="sandbox-token" app={app} />)
    await waitFor(() => expect(screen.getByText(MOTHER_HELP)).toBeTruthy())
    expect(screen.queryByText(MOTHER_IC_HELP)).toBeNull()
    // Her IC is uploaded and read; the server stops naming her.
    mockApi.listDocuments.mockResolvedValue({
      documents: [doc(1, 'parent_ic', 'father'), doc(2, 'parent_ic', 'mother'), mothersStr([])] })
    const input = cardOf(MOTHER_IC).querySelector('input[type="file"]') as HTMLInputElement
    await act(async () => {
      fireEvent.change(input, { target: { files: [new File(['x'], 'm.pdf', { type: 'application/pdf' })] } })
    })
    await waitFor(() => expect(screen.getByText(MOTHER_IC_HELP)).toBeTruthy())
    expect(screen.queryByText(MOTHER_HELP)).toBeNull()
    expect(screen.getAllByText(MOTHER_IC, { exact: false })).toHaveLength(1)
    view.unmount()
  })
})

describe('review F3 — an unreadable IC on her card gets its coach', () => {
  it('the per-file coach speaks on the mother\'s card (the cluster coach never covers a non-earner)', async () => {
    const unreadable = doc(2, 'parent_ic', 'mother', {
      vision_run_at: '2026-09-01T00:00:00Z', vision_fields: { student_verdict: 'unreadable' },
      income_ic_check: { nric: '', name: '', address: '', member: 'mother', name_status: 'pending', readable: false },
    })
    await student('str', [doc(1, 'parent_ic', 'father'), unreadable, mothersStr([], ['mother'])])
    const card = cardOf(MOTHER_IC)
    expect(card.querySelector('[data-testid="coach-2"]')).not.toBeNull()
    // …and the earner's IC keeps the ONE cluster coach, not a per-file one (unchanged)
    expect(screen.queryByTestId('coach-1')).toBeNull()
  })
})

describe('salary route — only the father ticked', () => {
  it('a block for the mother appears with her IC card, not required', async () => {
    await student('salary', [doc(1, 'parent_ic', 'father'), mothersStr(['mother'])])
    expect(screen.getByText(MOTHER_IC, { exact: false }).textContent).toBe(MOTHER_IC)
    expect(screen.getByText(MOTHER_HELP)).toBeTruthy()
    expect(screen.getAllByText(FATHER_IC, { exact: false })).toHaveLength(1)
  })

  it('...and none when the STR is settled', async () => {
    await student('salary', [doc(1, 'parent_ic', 'father'), mothersStr([])])
    expect(screen.queryByText(MOTHER_IC, { exact: false })).toBeNull()
  })
})
