/**
 * @jest-environment jsdom
 *
 * THE FIRST TEST THAT MOUNTS THIS COMPONENT.
 *
 * `ScholarshipDocuments.tsx` is ~1,900 lines and had never been rendered in a test — the closest
 * thing was `docFileLayout.test.ts`, which exercises one pure helper. Everything about which cards
 * a student sees was therefore unasserted, which is exactly how a hard-coded `COMPULSORY_DOC_TYPES`
 * could sit in `lib/scholarship.ts` disagreeing with the submission gate in production without a
 * single test going red.
 *
 * Scope: does the tab render what the PROGRAMME asks for, and does every document card use the
 * SAME file layout? Upload, deletion, the income wizard's route logic and the coach all have
 * their own homes and are not re-tested here. `t` echoes its key, so assertions read against i18n
 * keys rather than English copy — copy changes must not break this file.
 *
 * The second block arrived in code health H6, replacing the source-scanning half of
 * `lib/__tests__/docFileLayout.test.ts`. Its reason is written at the block.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import ScholarshipDocuments from './ScholarshipDocuments'
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
// The coaches fetch their own advice; they are not what this file is about.
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.listDocuments.mockResolvedValue({ documents: [] })
  mockApi.getConsentStatus.mockResolvedValue(
    { is_minor: false, consents: [] } as unknown as api.ConsentStatus,
  )
})

/** The fixture student, re-configured. Only `requirements` moves. */
const withRequirements = (requirements: ApplicationRequirements): ScholarshipApplication =>
  ({ ...sandboxApplication, requirements })

const FULL: ApplicationRequirements = {
  documents: {
    required: ['ic', 'income_proof', 'offer_letter', 'results_slip'],
    optional: ['electricity_bill', 'photo', 'school_leaving_cert', 'statement_of_intent',
               'water_bill'],
  },
}

/** Section headings are the honest signal for "is this whole block on the page". */
const HEAD = {
  identity: 'scholarship.docs.section.identity.title',
  academic: 'scholarship.docs.section.academic.title',
  pathway: 'scholarship.docs.section.pathway.title',
  income: 'scholarship.docs.section.income.title',
  other: 'scholarship.docs.section.other.title',
}

const render_ = async (app: ScholarshipApplication) => {
  render(<ScholarshipDocuments token="sandbox-token" app={app} />)
  await waitFor(() => expect(screen.getByText(HEAD.identity)).toBeTruthy())
}

describe('what the programme asks for decides what is drawn', () => {
  it('renders every section when the programme asks for everything', async () => {
    await render_(withRequirements(FULL))
    for (const head of Object.values(HEAD)) {
      expect(screen.getByText(head)).toBeTruthy()
    }
  })

  it('drops a section whose only document is switched off', async () => {
    // A heading over nothing reads as a page that failed to load, so the whole section goes.
    await render_(withRequirements({
      documents: {
        required: FULL.documents.required.filter((d) => d !== 'offer_letter'),
        optional: FULL.documents.optional,
      },
    }))
    expect(screen.queryByText(HEAD.pathway)).toBeNull()
    // ...and its neighbours are untouched. Without this the test also passes if the page
    // rendered nothing at all.
    expect(screen.getByText(HEAD.academic)).toBeTruthy()
    expect(screen.getByText(HEAD.income)).toBeTruthy()
  })

  it('drops the WHOLE income section when the programme does not means-test', async () => {
    // `income_proof` is one switch over the route engine, not a card. Half an income section —
    // the father's IC without his payslip — would be an assessment nobody designed.
    await render_(withRequirements({
      documents: {
        required: FULL.documents.required.filter((d) => d !== 'income_proof'),
        optional: FULL.documents.optional,
      },
    }))
    expect(screen.queryByText(HEAD.income)).toBeNull()
    expect(screen.getByText(HEAD.identity)).toBeTruthy()
  })

  it('drops the Other bucket only when every one of its documents is off', async () => {
    await render_(withRequirements({
      documents: { required: FULL.documents.required, optional: ['water_bill'] },
    }))
    expect(screen.queryByText(HEAD.other)).toBeNull()
  })

  it('keeps the Other bucket when one of its documents survives', async () => {
    await render_(withRequirements({
      documents: { required: FULL.documents.required, optional: ['photo'] },
    }))
    expect(screen.getByText(HEAD.other)).toBeTruthy()
  })

  it('renders the leanest possible programme without collapsing', async () => {
    // Identity and results only. This is the shape a second tenant is most likely to land on,
    // and the one nobody looks at while BrightPath is the only organisation.
    await render_(withRequirements({
      documents: { required: ['ic', 'results_slip'], optional: [] },
    }))
    expect(screen.getByText(HEAD.identity)).toBeTruthy()
    expect(screen.getByText(HEAD.academic)).toBeTruthy()
    expect(screen.queryByText(HEAD.pathway)).toBeNull()
    expect(screen.queryByText(HEAD.income)).toBeNull()
    expect(screen.queryByText(HEAD.other)).toBeNull()
  })

  it('renders EVERYTHING when the payload carries no requirements block at all', async () => {
    // ⚠ The Sprint 3a failure shape at the render layer. A payload from before 3b — or any future
    // path that forgets the field — must not blank the page. "We were not told" degrades to
    // showing every card and asserting nothing, never to showing none.
    const { requirements: _dropped, ...withoutBlock } = sandboxApplication
    await render_(withoutBlock as ScholarshipApplication)
    for (const head of Object.values(HEAD)) {
      expect(screen.getByText(head)).toBeTruthy()
    }
  })
})

/**
 * ⚠ THIS BLOCK REPLACES the source-scanning half of `src/lib/__tests__/docFileLayout.test.ts`,
 * which grepped this component for a revived `MULTI_INSTANCE` constant.
 *
 * THE BUG IT REPLACES (2026-07-26). "Tidier document rows" gave every document card a bordered
 * chip with Replace + Remove grouped INSIDE it — except `str` / `salary_slip` / `epf`, which it
 * exempted as "multi-file". That exemption mirrored `DocumentListCreateView.MULTI_INSTANCE_DOC_TYPES`,
 * a backend rule already RETIRED on 2026-06-05 (every doc type is single-instance; an upload
 * replaces its `(doc_type, household_member)` slot). So the mother's STR and salary-slip cards
 * alone kept Replace up in the header, beside a bare unbordered filename.
 *
 * A text scan could only ever catch a re-introduced constant by NAME. What actually matters is
 * where Replace sits, and that is now asserted from the DOM — for the three types that were
 * exempted and, as the control, for one that never was.
 */
describe('no income-proof document gets its own layout', () => {
  const doc = (id: number, docType: string, member = '', filename?: string) => ({
    id, doc_type: docType, household_member: member,
    original_filename: filename ?? `test-${docType}.pdf`,
    content_type: 'application/pdf', size: 1234, verification_status: 'pending',
    download_url: 'https://example.test/d', uploaded_at: '2026-06-01',
  }) as unknown as api.ApplicantDocument

  /** The bordered file row: the nearest ancestor of the filename that also holds Remove. That IS
   *  the chip — one row carrying the file and its actions together. */
  const fileRow = (filename: string): HTMLElement => {
    let el: HTMLElement | null = screen.getByText(filename)
    while (el && !within(el).queryByText('scholarship.docs.remove')) el = el.parentElement
    if (!el) throw new Error(`no file row around ${filename} — nothing holds its Remove action`)
    return el
  }

  /** The student, on one of the two income routes, with the given files already uploaded. */
  const withRoute = async (route: 'salary' | 'str', documents: api.ApplicantDocument[]) => {
    mockApi.listDocuments.mockResolvedValue({ documents })
    await render_({
      ...sandboxApplication, requirements: FULL, income_route: route, income_earner: 'father',
      income_working_members: ['father'],
    } as unknown as ScholarshipApplication)
  }

  it('STR renders through the same chip as the applicant IC', async () => {
    await withRoute('str', [doc(1, 'ic'), doc(2, 'str', 'father')])
    for (const name of ['test-ic.pdf', 'test-str.pdf']) {
      expect(within(fileRow(name)).getByText('scholarship.docs.replace')).toBeTruthy()
    }
  })

  it('the salary slip and the EPF statement do too', async () => {
    await withRoute('salary', [doc(1, 'ic'), doc(3, 'salary_slip', 'father'),
                               doc(4, 'epf', 'father')])
    for (const name of ['test-ic.pdf', 'test-salary_slip.pdf', 'test-epf.pdf']) {
      expect(within(fileRow(name)).getByText('scholarship.docs.replace')).toBeTruthy()
    }
  })

  it('⚠ AND THE RULE STILL TAKES ONLY A COUNT — two files on one card drop Replace', async () => {
    // Reachable during the TD-115 slot backfill: an STR earner's card shows the legacy untagged
    // copy beside the member-tagged one. Without this the assertions above would also pass on a
    // component that simply put Replace in every row for ever, and the layout rule would be
    // untested in the one direction it can still vary.
    await withRoute('str', [doc(2, 'str', 'father'), doc(5, 'str', '', 'legacy-str.pdf')])
    for (const name of ['test-str.pdf', 'legacy-str.pdf']) {
      expect(within(fileRow(name)).queryByText('scholarship.docs.replace')).toBeNull()
      expect(within(fileRow(name)).getByText('scholarship.docs.remove')).toBeTruthy()
    }
  })
})
