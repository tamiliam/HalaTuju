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
import { act, render, screen, waitFor, within } from '@testing-library/react'
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

/**
 * THE PER-EARNER INCOME TICK — what a student SEES, against what the server counts.
 *
 * This is TD-262 / W7 (and W6), moved out of `lib/__tests__/incomeEvidenceHomes.test.ts`, where it
 * could only be a SOURCE READ: `memberIncomeShown` is a closure inside this component. Every
 * assertion below reads the cue the student reads — the "income shown" line that replaces "add any
 * one of these" and turns the block green — never an internal flag.
 *
 * The rule, which is the server's (`income_engine.member_income_evidenced`, arms 1-3, and
 * `has_income_support_doc`): a salary slip, an EPF, or a declared amount backed by a supporting
 * letter that is tagged to this earner OR UNTAGGED and that READ.
 *
 * ⚠ AND NO STR ARM. `member_income_evidenced` has a fourth, `str_not_breached`, which is about the
 * HOUSEHOLD; the owner ruled on 2026-09-19 that an STR must not tick an individual EARNER (the
 * working adults' proofs are ADDITIONAL to it). The STR case below pins that as CORRECT.
 */
describe('the per-earner income tick counts what the server counts', () => {
  const SHOWN = 'scholarship.docs.income.wizard.incomeShown'
  const NOT_SHOWN = 'scholarship.docs.income.wizard.incomeAnyOne'

  /** A supporting letter, with the read-verdict the extractor stored for it. */
  const letter = (id: number, member: string, studentVerdict = 'ok') => ({
    id, doc_type: 'income_support_doc', household_member: member,
    original_filename: `letter-${id}.pdf`, content_type: 'application/pdf', size: 2048,
    verification_status: 'pending', download_url: 'https://example.test/d',
    uploaded_at: '2026-06-01', vision_fields: { student_verdict: studentVerdict },
  }) as unknown as api.ApplicantDocument

  /** A current, matching STR for the father — everything the household needs for the gate. */
  const householdStr = () => ({
    id: 90, doc_type: 'str', household_member: 'father',
    original_filename: 'household-str.pdf', content_type: 'application/pdf', size: 2048,
    verification_status: 'pending', download_url: 'https://example.test/d',
    uploaded_at: '2026-06-01',
    str_check: { current_status: 'current', name_status: 'match', nric_status: 'match' },
  }) as unknown as api.ApplicantDocument

  /** A salary-route student: who works, what each declared, and what is on file. */
  const salaryStudent = async (
    members: Array<'father' | 'mother'>,
    declared: Record<string, number>,
    documents: api.ApplicantDocument[],
  ) => {
    mockApi.listDocuments.mockResolvedValue({ documents })
    await render_({
      ...sandboxApplication, requirements: FULL, income_route: 'salary', income_earner: '',
      income_working_members: members, income_declared: declared,
    } as unknown as ScholarshipApplication)
  }

  it('a declared amount + an UNTAGGED letter that read: the earner reads as shown', async () => {
    // W7. `has_income_support_doc` filters `household_member__in=[member, '']` — an Action-Centre
    // upload routinely lands untagged, and one family-level letter is enough (D1). Before this
    // fix the server counted it, the officer saw it, and her own screen went on asking.
    await salaryStudent(['father'], { father: 900 }, [letter(11, '')])
    expect(screen.getByText(SHOWN)).toBeTruthy()
    expect(screen.queryByText(NOT_SHOWN)).toBeNull()
  })

  it('a declared amount + a letter TAGGED to that earner: shown', async () => {
    await salaryStudent(['father'], { father: 900 }, [letter(12, 'father')])
    expect(screen.getByText(SHOWN)).toBeTruthy()
  })

  it('a letter tagged to a DIFFERENT earner does not tick this one', async () => {
    // The untagged arm widens the rule to household-level; it does not erase whose letter it is.
    await salaryStudent(['father'], { father: 900 }, [letter(13, 'mother')])
    expect(screen.getByText(NOT_SHOWN)).toBeTruthy()
    expect(screen.queryByText(SHOWN)).toBeNull()
  })

  it('a declared amount with NO letter is not shown — a self-report is not evidence', async () => {
    await salaryStudent(['father'], { father: 900 }, [])
    expect(screen.getByText(NOT_SHOWN)).toBeTruthy()
  })

  it('a letter that did NOT read is not evidence either', async () => {
    // The api's V1 finding-#2 rule: `has_income_support_doc` requires `student_verdict == 'ok'`,
    // so a blank or wrong image cannot "prove" a declared informal wage. The student payload
    // carries `vision_fields`, so the cue asks the same question rather than counting presence.
    await salaryStudent(['father'], { father: 900 }, [letter(14, '', 'wrong_doc')])
    expect(screen.getByText(NOT_SHOWN)).toBeTruthy()
    expect(screen.queryByText(SHOWN)).toBeNull()
  })

  it('⚠ A HOUSEHOLD STR AND NOTHING ELSE LEAVES THE EARNER UN-TICKED — the owner\'s rule', async () => {
    // W6, pinned as CORRECT (owner 2026-09-19, docs/decisions.md). The STR clears the submission
    // gate and predicts green; it is not a statement about what this father earns, and his income
    // proof is ADDITIONAL to it. DO NOT "fix" this by adding an STR arm to `memberIncomeShown`.
    await salaryStudent(['father'], {}, [householdStr()])
    expect(screen.getByText(NOT_SHOWN)).toBeTruthy()
    expect(screen.queryByText(SHOWN)).toBeNull()
  })

  it('⚠ ONE UNTAGGED LETTER TICKS BOTH EARNERS — the api counts the same row for each', async () => {
    // Stated because it looks like a bug. `has_income_support_doc` filters per member and never
    // claims a document, so the identical row satisfies the father AND the mother. The cue reads
    // as the GATE reads; it must not invent a stricter rule than the one that lets her submit.
    // (The OFFICER's panel does claim an untagged letter once — that disagreement is TD-262
    // chunk 2, and `incomeEvidenceHomes.test.ts` W-B pins the cockpit's side of it.)
    await salaryStudent(['father', 'mother'], { father: 900, mother: 700 }, [letter(15, '')])
    expect(screen.getAllByText(SHOWN)).toHaveLength(2)
    expect(screen.queryByText(NOT_SHOWN)).toBeNull()
  })
})

/**
 * THE THREE DOORWAYS — TD-262 F2, and the lockout that used to bolt the third one shut.
 *
 * The owner's rule since 2026-07-25 is that a household shows an earner's income ANY ONE way.
 * The screen did not say that: it drew two upload cards and hid the third way — the amount a
 * cash earner is paid, plus one simple letter — behind a text link reading like an admission of
 * failure. It is now a card of equal weight beside the other two, closed until tapped.
 *
 * ⚠ AND THE HALF THAT MATTERED MOST. The cash panel was hidden whenever ANY salary or EPF FILE
 * existed for that earner. So the family whose only payslip was a photograph of the wrong thing
 * — the family this door was built for — had it closed by the very document that proved
 * nothing. The gate is now the SERVED answer from `apps/scholarship/income_shown.py`, the same
 * one the submission gate and the officer's chase list read, with the old presence reading kept
 * as the fallback for a payload that predates it.
 *
 * Every assertion below reads what the student reads.
 */
describe('the third doorway: paid in cash, and the lockout that hid it', () => {
  const CASH_DOOR = 'scholarship.docs.income.wizard.declared.cantGet'
  const PROMPT = 'scholarship.docs.income.wizard.declared.prompt'
  const ONE_LETTER = 'scholarship.docs.income.wizard.declared.oneLetterWholeFamily'
  const LETTER_CARD = 'scholarship.docs.income.wizard.supportLetterTitle'
  const SLIP_CARD = 'scholarship.docs.income.wizard.salaryTitle.father'
  const EPF_CARD = 'scholarship.docs.income.wizard.epfTitle.father'
  const SHOWN = 'scholarship.docs.income.wizard.incomeShown'

  const slip = (id: number, member = 'father') => ({
    id, doc_type: 'salary_slip', household_member: member,
    original_filename: `slip-${id}.pdf`, content_type: 'application/pdf', size: 2048,
    verification_status: 'pending', download_url: 'https://example.test/d',
    uploaded_at: '2026-06-01',
  }) as unknown as api.ApplicantDocument

  /** A payslip the server judged unusable — a MyKad in the payslip slot (#47). */
  const duffSlip = (id: number) => ({
    ...slip(id), authenticity: { status: 'not_salary' },
  }) as unknown as api.ApplicantDocument

  /** What the api serves for the father: `apps/scholarship/income_shown.py`'s answer. */
  const served = (a: { shown?: boolean; way?: string | null; documents?: number[]
    unusable?: Array<{ doc_id: number; doc_type: string; reason: string }> }) => ({
    father: { shown: false, way: null, documents: [], unusable: [], ...a },
    mother: { shown: false, way: null, documents: [], unusable: [] },
  }) as unknown as ScholarshipApplication['income_shown']

  /** The third card's own toggle — the card is a button wrapping its title and help line. */
  const cashDoorToggle = (): HTMLButtonElement => {
    const btn = screen.getByText(CASH_DOOR).closest('button')
    if (!btn) throw new Error('the cash door is not a button — it cannot be opened by tapping')
    return btn as HTMLButtonElement
  }

  const student = async (opts: {
    declared?: Record<string, number>
    documents?: api.ApplicantDocument[]
    income_shown?: ScholarshipApplication['income_shown']
  }) => {
    mockApi.listDocuments.mockResolvedValue({ documents: opts.documents ?? [] })
    await render_({
      ...sandboxApplication, requirements: FULL, income_route: 'salary', income_earner: '',
      income_working_members: ['father'], income_declared: opts.declared ?? {},
      ...('income_shown' in opts ? { income_shown: opts.income_shown } : {}),
    } as unknown as ScholarshipApplication)
  }

  it('draws three doorways, and the third one starts closed', async () => {
    await student({ income_shown: served({}) })
    for (const card of [SLIP_CARD, EPF_CARD, CASH_DOOR]) {
      expect(screen.getByText(card)).toBeTruthy()
    }
    // Closed: the card is there, its contents are not.
    expect(screen.queryByText(PROMPT)).toBeNull()
    expect(cashDoorToggle().getAttribute('aria-expanded')).toBe('false')
  })

  it('opens in place on a tap — the amount field, and nothing she has not asked for', async () => {
    await student({ income_shown: served({}) })
    act(() => { cashDoorToggle().click() })
    expect(screen.getByText(PROMPT)).toBeTruthy()
    expect(screen.getByPlaceholderText('scholarship.docs.income.wizard.declared.placeholder'))
      .toBeTruthy()
    // ⚠ The letter card waits for an amount to support. An upload slot with nothing behind it
    // is one more thing to find, which is exactly the wall this door exists to avoid.
    expect(screen.queryByText(LETTER_CARD)).toBeNull()
  })

  it('a family who already typed a figure finds their answer open, with the letter card', async () => {
    await student({ declared: { father: 900 }, income_shown: served({}) })
    expect(screen.getByText(PROMPT)).toBeTruthy()
    expect(screen.getByText(LETTER_CARD)).toBeTruthy()
  })

  it('says, once, that one letter covers the whole family', async () => {
    // Nothing on the screen said so, and a family with two cash earners had every reason to
    // assume a letter each. The api counts one untagged letter for every earner (W7).
    await student({ income_shown: served({}) })
    expect(screen.getByText(ONE_LETTER)).toBeTruthy()
  })

  it('⚠ THE LOCKOUT: an UNUSABLE payslip no longer closes the door', async () => {
    // The family this door was built for. Their one payslip is a photograph of the wrong thing;
    // the server says their income is NOT shown, and before F2 the only screen that could fix
    // that had hidden the way in. Presence is not evidence.
    await student({
      documents: [duffSlip(21)],
      income_shown: served({ unusable: [{ doc_id: 21, doc_type: 'salary_slip', reason: 'not_salary' }] }),
    })
    expect(screen.getByText(CASH_DOOR)).toBeTruthy()
  })

  it('...and a payslip that DID read still closes it — nothing more is needed there', async () => {
    // The control. Without this the test above also passes on a screen that simply offers the
    // cash door to everybody for ever, and the rule would be untested in the only direction it
    // can still vary.
    await student({
      documents: [slip(22)],
      income_shown: served({ shown: true, way: 'salary_slip', documents: [22] }),
    })
    expect(screen.queryByText(CASH_DOOR)).toBeNull()
    expect(screen.getByText(SHOWN)).toBeTruthy()
  })

  it('⚠ a declared amount that IS accepted keeps its own door open', async () => {
    // `declared_letter` is the cash way itself. Closing on it would hide the family's own typed
    // figure and the letter beneath it at the moment they finished — the door swinging shut
    // behind them.
    await student({
      declared: { father: 900 },
      documents: [],
      income_shown: served({ shown: true, way: 'declared_letter', documents: [31] }),
    })
    expect(screen.getByText(CASH_DOOR)).toBeTruthy()
    expect(screen.getByText(PROMPT)).toBeTruthy()
  })

  it('an api that serves nothing leaves the screen exactly as it was', async () => {
    // The two services deploy together but not atomically. A cached payload, or an api one
    // revision behind, must fall back to the OLD presence reading rather than re-opening a door
    // for every household at once.
    await student({ documents: [slip(23)] })          // no `income_shown` at all
    expect(screen.queryByText(CASH_DOOR)).toBeNull()
  })

  it('...and with nothing on file that fallback still offers the door', async () => {
    await student({ documents: [] })
    expect(screen.getByText(CASH_DOOR)).toBeTruthy()
  })
})
