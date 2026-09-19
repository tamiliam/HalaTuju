/**
 * Code health H8 — THE WEB HALF OF THE CHARACTERISATION, and the CROSS-LANGUAGE TABLE.
 *
 * Its twin is `halatuju_api/apps/scholarship/tests/test_income_evidence_homes.py`, which puts the
 * same households through every api home of "has this household shown what it earns?". This file
 * puts them through every WEB home, and then — the point of the exercise — asserts, scenario by
 * scenario, whether the two languages AGREE.
 *
 * ⚠ NOTHING HERE ASSERTS WHAT THE CODE SHOULD DO. Every expected value was read off the tree as it
 * stands on 2026-09-19. Where the web and the api disagree, the disagreement is PINNED with an
 * `H8-FINDING` comment and reported — never reconciled by editing a number here. This is an
 * eligibility path: the web decides what a student is asked for and what an officer chases, and a
 * silent change to either is a change to a real household's experience.
 *
 * THE WEB HOMES (see the sprint report for the full map with file:line)
 *   W-A  `incomeWizard.incomeRequirements` / `salaryMemberBlocks` — declared a "Pure mirror of the
 *        backend income requirement engine". What shall we ASK FOR.
 *   W-B  `officerCockpit.incomeSubSections` — what the OFFICER is shown, including which earners
 *        get a red "Missing" row. Imports W-A for the member list, then decides evidence itself.
 *   W-C  `docCategory.docTypeToFact` (via `groupDocumentsByFact`) — which fact section a document
 *        is filed under. TWO further copies of this map existed until TD-262 chunk 1; all three
 *        readers now share one home and this file pins the whole table plus both folds.
 *   W-D  `ScholarshipDocuments.memberIncomeShown` — the STUDENT's green cue. Not exported (it is a
 *        closure inside the component), so its SHAPE is characterised here by a source-read pin;
 *        what a student actually sees is asserted by rendering the tab in
 *        `src/components/ScholarshipDocuments.test.tsx`.
 *
 * The api answers quoted below are not guesses: each is the value asserted by the named test in
 * `test_income_evidence_homes.py`, which runs against the real engine.
 */
import { readFileSync } from 'fs'
import { join } from 'path'

import {
  docTypeToFact, docTypeToRequestFact, docTypeToStudentGroup, STUDENT_DOC_GROUP_ORDER,
} from '@/lib/docCategory'
import { groupDocumentsByFact, incomeSubSections } from '@/lib/officerCockpit'
import { incomeRequirements, salaryMemberBlocks, workingMembers } from '@/lib/incomeWizard'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import type { IncomeShownAnswer, IncomeShownMap } from '@/lib/incomeShown'

const WEB_ROOT = join(__dirname, '..', '..', '..')

function doc(over: Partial<AdminApplicantDocument> = {}): AdminApplicantDocument {
  return {
    id: 1,
    doc_type: 'ic',
    original_filename: 'fake.pdf',
    content_type: 'application/pdf',
    size: 1024,
    verification_status: 'pending',
    download_url: null,
    vision_nric: '',
    vision_name: '',
    vision_address: '',
    vision_run_at: null,
    vision_error: '',
    vision_nric_verdict: '',
    vision_name_verdict: '',
    vision_name_match: '',
    vision_address_match: '',
    ...over,
  }
}

/** The cockpit's salary rows as `[docType, member, docId|null]`, which is how a disagreement
 *  about evidence becomes visible: `income_evidence` with a null doc IS the red Missing row. */
const salaryRows = (app: Parameters<typeof incomeSubSections>[0], docs: AdminApplicantDocument[]) =>
  incomeSubSections(app, docs).salary.map((s) => [s.docType, s.member, s.doc?.id ?? null])

/** The served reason codes, keyed by the document they were served against. */
const salaryUnusable = (app: Parameters<typeof incomeSubSections>[0], docs: AdminApplicantDocument[]) =>
  Object.fromEntries(incomeSubSections(app, docs).salary
    .filter((s) => s.doc && s.unusable)
    .map((s) => [s.doc!.id, s.unusable]))

const SALARY_FATHER = { income_route: 'salary', income_earner: '', income_working_members: ['father'] }

/** `SALARY_FATHER` plus the api's served per-earner answer for the father (TD-262 chunks 2+3).
 *  Its shape is pinned against the real api by
 *  `test_income_evidence_homes.TestServedPerEarnerAnswer`. */
const served = (answer: Partial<IncomeShownAnswer>) => ({
  ...SALARY_FATHER,
  income_shown: {
    father: { shown: false, way: null, documents: [], unusable: [], ...answer },
  } as IncomeShownMap,
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// W-A — the requirement engine, and where the "pure mirror" is not one
// ════════════════════════════════════════════════════════════════════════════════════════════
describe('W-A incomeRequirements — what the student is asked for', () => {
  it('draws exactly the api list on the salary route: IC compulsory, payslip + EPF optional', () => {
    // api twin: TestEachWayAlone.test_way1_usable_payslip asserts
    //   (['parent_ic'], ['salary_slip', 'epf'])  for the same household.
    const blocks = salaryMemberBlocks(['father'])
    expect(blocks).toHaveLength(1)
    expect(blocks[0].compulsory.map((d) => d.docType)).toEqual(['parent_ic'])
    expect(blocks[0].optional.map((d) => d.docType)).toEqual(['salary_slip', 'epf'])
    expect(blocks[0].relDoc).toBe('')
  })

  it('draws the mother the birth certificate and the guardian the letter, as the api does', () => {
    expect(salaryMemberBlocks(['mother'])[0].compulsory.map((d) => d.docType))
      .toEqual(['parent_ic', 'birth_certificate'])
    expect(salaryMemberBlocks(['guardian'])[0].compulsory.map((d) => d.docType))
      .toEqual(['parent_ic', 'guardianship_letter'])
  })

  it('draws the api STR triplet on the STR route', () => {
    // api twin: TestHouseholdShapes.test_str_route_draws_the_str_triplet_and_never_the_letter.
    const r = incomeRequirements({ income_route: 'str', income_earner: 'father' })
    expect(r.compulsory).toEqual(['parent_ic', 'str'])
    expect(r.optional).toEqual(['water_bill', 'electricity_bill', 'salary_slip', 'epf'])
    expect(r.members).toEqual([])
  })

  it('never offers the support letter — on either route, exactly as the api never does', () => {
    // H8-FINDING (F2, both languages): `income_support_doc` is the ONLY document that carries the
    // owner's fourth way (a declared amount + a supporting letter), and NEITHER requirement engine
    // lists it. A student can reach it only through an Action-Centre request. Both sides agree, so
    // this is not drift — it is the same gap, twice.
    for (const route of ['salary', 'str'] as const) {
      const r = incomeRequirements({
        income_route: route, income_earner: 'father', income_working_members: ['father'] })
      const all = [...r.compulsory, ...r.optional, ...r.members.flatMap(
        (b) => [...b.compulsory, ...b.optional].map((d) => d.docType))]
      expect(all).not.toContain('income_support_doc')
    }
  })

  it('H8-FINDING (W1): the "pure mirror" carries an arm the api engine does not have', () => {
    // A MONONYM student (no A/L, A/P, bin, binti in the name) cannot prove the father link off the
    // shared patronymic, so this file offers a household birth certificate as an OPTIONAL extra.
    // `income_engine.income_requirements` has NO patronymic branch at all — its salary-route
    // optional list is unconditionally ['water_bill', 'electricity_bill'] (pinned by the api twin
    // TestEachWayAlone.test_way1_usable_payslip / TestHouseholdShapes.test_blank_wizard_...).
    // The drift is BENIGN in direction — the extra card is optional, so nobody is newly blocked —
    // but a file whose header says "Pure mirror … Keep the two in lockstep" has been out of
    // lockstep since the #55 / DIVIYA fix, and nothing would have said so.
    const mononym = incomeRequirements(
      { income_route: 'salary', income_working_members: ['father'] },
      { studentHasPatronymic: false })
    expect(mononym.optional).toEqual(['water_bill', 'electricity_bill', 'birth_certificate'])

    const normal = incomeRequirements(
      { income_route: 'salary', income_working_members: ['father'] })
    expect(normal.optional).toEqual(['water_bill', 'electricity_bill'])   // ← the api's only answer
  })

  it('reads the member list the way the api reads it (order + de-dupe + garbage tolerance)', () => {
    // api twin: income_engine.working_members.
    expect(workingMembers(['sister', 'father', 'father'])).toEqual(['father', 'sister'])
    expect(workingMembers(null)).toEqual([])
  })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// W-B — the officer's income panel decides evidence by PRESENCE; the api decides it by READING
// ════════════════════════════════════════════════════════════════════════════════════════════
describe('W-B incomeSubSections — what the officer chases', () => {
  it('draws a red Missing row when the earner has shown nothing, as the gate blocks her', () => {
    // api twin: TestNearMisses.test_nothing_at_all — served False, gate blocks.
    expect(salaryRows(SALARY_FATHER, [])).toEqual([
      ['income_evidence', 'father', null],
      ['parent_ic', 'father', null],
    ])
  })

  it('a usable payslip fills the slot — agrees with the api', () => {
    // api twin: TestEachWayAlone.test_way1_usable_payslip — served True.
    const rows = salaryRows(SALARY_FATHER, [
      doc({ id: 7, doc_type: 'salary_slip', household_member: 'father' })])
    expect(rows[0]).toEqual(['salary_slip', 'father', 7])
  })

  it('W2 FIXED: a not_salary photo is LISTED, marked not usable, and the Missing row stands', () => {
    // api twin: TestNearMisses.test_not_salary_photo_in_the_payslip_slot_is_not_evidence —
    // `usable_salary_slip` refuses it (the #47 fix) and the gate emits
    // `income_evidence_missing:father`. This panel used to ask only `find('salary_slip', m)`,
    // which is PRESENCE, so it showed the father's income evidence as satisfied with no Missing
    // row about a household the submission gate was holding shut.
    // Real student: application 73 — a MyKad photographed into the payslip slot.
    const docs = [doc({ id: 7, doc_type: 'salary_slip', household_member: 'father',
                        authenticity: { status: 'not_salary', reason: 'reads as a MyKad' } })]
    const app = served({ unusable: [{ doc_id: 7, doc_type: 'salary_slip', reason: 'not_salary' }] })
    // The document STILL SHOWS — the officer must see what the family sent — and the red
    // Missing row appears beside it.
    expect(salaryRows(app, docs).slice(0, 2)).toEqual([
      ['salary_slip', 'father', 7],
      ['income_evidence', 'father', null],
    ])
    expect(salaryUnusable(app, docs)).toEqual({ 7: 'not_salary' })
  })

  it('W3 FIXED: an EPF that reads nothing is LISTED as not usable, with the Missing row', () => {
    // api twin: TestNearMisses.test_unreadable_epf_is_not_evidence — `_member_has_epf_value`
    // requires a derivable monthly figure (owner 2026-07-25: "a readable EPF"), so the gate
    // blocks. This panel used to ask only `find('epf', m)`.
    const docs = [doc({ id: 8, doc_type: 'epf', household_member: 'father' })]
    const app = served({ unusable: [{ doc_id: 8, doc_type: 'epf', reason: 'no_value' }] })
    expect(salaryRows(app, docs).slice(0, 2)).toEqual([
      ['epf', 'father', 8],
      ['income_evidence', 'father', null],
    ])
    expect(salaryUnusable(app, docs)).toEqual({ 8: 'no_value' })
  })

  it('W4 FIXED: a support letter with NO declared amount and NO read is not usable', () => {
    // api twin: TestNearMisses.test_letter_without_a_declared_amount_is_not_evidence (served
    // False) and `has_income_support_doc`, which additionally requires the letter to have READ
    // (`student_verdict == 'ok'` — the V1 finding #2 fix, so a blank image cannot "prove" a wage).
    // This panel required neither, so a student who uploaded a blank letter and declared nothing
    // saw her submission blocked while the officer's panel showed her income evidenced.
    const docs = [doc({ id: 9, doc_type: 'income_support_doc', household_member: 'father' })]
    const app = served({
      unusable: [{ doc_id: 9, doc_type: 'income_support_doc', reason: 'letter_unread' }] })
    expect(salaryRows(app, docs).slice(0, 2)).toEqual([
      ['income_support_doc', 'father', 9],
      ['income_evidence', 'father', null],
    ])
    expect(salaryUnusable(app, docs)).toEqual({ 9: 'letter_unread' })
  })

  it('a usable document served as SHOWN draws no Missing row and carries no reason', () => {
    const docs = [doc({ id: 7, doc_type: 'salary_slip', household_member: 'father' })]
    const app = served({ shown: true, way: 'salary_slip', documents: [7] })
    expect(salaryRows(app, docs)).toEqual([
      ['salary_slip', 'father', 7],
      ['parent_ic', 'father', null],
    ])
    expect(salaryUnusable(app, docs)).toEqual({})
  })

  it('⚠ NO SERVED ANSWER → TODAY\'S PRESENCE READING, never a screen full of red', () => {
    // The two services deploy together but NOT atomically, so a cached payload or an api one
    // revision behind must leave this panel exactly as it was — a per-earner answer that is
    // absent means "we were not told", never "nothing is evidenced".
    const docs = [doc({ id: 7, doc_type: 'salary_slip', household_member: 'father',
                        authenticity: { status: 'not_salary', reason: 'reads as a MyKad' } })]
    expect(salaryRows(SALARY_FATHER, docs)).toEqual([
      ['salary_slip', 'father', 7],
      ['parent_ic', 'father', null],
    ])
    expect(salaryUnusable(SALARY_FATHER, docs)).toEqual({})
    // …and a malformed one degrades the same way rather than throwing.
    const junk = { ...SALARY_FATHER, income_shown: { father: null } as unknown as IncomeShownMap }
    expect(salaryRows(junk, docs)[0]).toEqual(['salary_slip', 'father', 7])
  })

  it('agrees with the api that an untagged household letter may carry an earner', () => {
    // api twin: `has_income_support_doc` accepts `household_member__in=[member, '']`. The cockpit
    // does the same through `supportFor`, and claims it once so two earners cannot share one.
    const rows = salaryRows(
      { ...SALARY_FATHER, income_working_members: ['father', 'mother'] },
      [doc({ id: 9, doc_type: 'income_support_doc', household_member: '' })])
    const carrying = rows.filter((r) => r[2] === 9)
    expect(carrying).toHaveLength(1)
  })

  it('a non-breached STR makes the salary rows supportive — no Missing placeholders', () => {
    // api twin: TestEachWayAlone.test_way4_non_breached_household_str — `str_not_breached` is the
    // fourth way, and the gate clears. `strNotBreached` here reproduces that predicate, and the
    // two agree: no red row is drawn.
    const rows = salaryRows(SALARY_FATHER, [
      doc({ id: 3, doc_type: 'str', household_member: 'father',
            str_check: { current_status: 'current' } as AdminApplicantDocument['str_check'] })])
    expect(rows.filter((r) => r[0] === 'income_evidence')).toEqual([])
  })

  it('a rejected STR drops the household back into full salary documentation, as the api does', () => {
    // api twin: TestStrLadder.test_rejected_str_does_not_evidence_income.
    const rows = salaryRows(SALARY_FATHER, [
      doc({ id: 3, doc_type: 'str', household_member: 'father',
            str_check: { current_status: 'rejected' } as AdminApplicantDocument['str_check'] })])
    expect(rows.filter((r) => r[0] === 'income_evidence')).toEqual([['income_evidence', 'father', null]])
  })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// W-C — WHICH FACT a document is filed under. ONE map now, and the readers that fold it
// ════════════════════════════════════════════════════════════════════════════════════════════
/**
 * ⚠ W5 IS FIXED (TD-262 chunk 1) AND THIS BLOCK IS NO LONGER A SOURCE READ. There were three
 * copies of "which fact does this document type belong to" — `officerCockpit.docTypeToFact`,
 * `view.tsx`'s `DOC_FACT` (a document REQUEST's stored fact) and `ScholarshipReview.tsx`'s
 * `DOC_CATEGORY` (the student's post-consent read-back) — and only the first had gained
 * `income_support_doc` when TD-235 incident 2 was fixed on 2026-09-07. The student's own
 * confirmation screen therefore filed the one document proving her family's informal income
 * under "Additional documents". All three now read `@/lib/docCategory`, so this pins BEHAVIOUR
 * through real imports rather than grepping two module-private consts.
 *
 * The table below is the characterisation: every value of `ApplicantDocument.DOC_TYPES`
 * (`halatuju_api/apps/scholarship/models.py`) with the officer-drawer bucket it lands in. The
 * two student-facing readers fold `additional` into `other` and are asserted against that fold,
 * so a difference has to be a decision rather than a map somebody forgot.
 */
const DOC_TYPE_FACT: Record<string, ReturnType<typeof docTypeToFact>> = {
  ic: 'identity',
  results_slip: 'academic',
  semester_result: 'academic',
  offer_letter: 'pathway',
  parent_ic: 'income',
  str: 'income',
  epf: 'income',
  salary_slip: 'income',
  income_support_doc: 'income',
  birth_certificate: 'income',
  guardianship_letter: 'income',
  water_bill: 'income',
  electricity_bill: 'income',
  school_leaving_cert: 'additional',
  statement_of_intent: 'additional',
  photo: 'additional',
  bank_statement: 'other',
  reference_letter: 'other',
  other: 'other',
}

describe('W-C the fact grouping — one rule, one home, three readers', () => {
  it('the cockpit files the support letter under income (the 2026-09-07 fix)', () => {
    const groups = groupDocumentsByFact([doc({ id: 1, doc_type: 'income_support_doc' })])
    expect(groups.income).toHaveLength(1)
    expect(groups.other).toHaveLength(0)
  })

  it('W5 RESOLVED: all three readers now file the support letter under income', () => {
    // The officer's drawer, the student's read-back, and the fact stamped on a document REQUEST.
    // Real student: Janani — the same letter, the same word, in three components, corrected in
    // one of them.
    expect(docTypeToFact('income_support_doc')).toBe('income')
    expect(docTypeToStudentGroup('income_support_doc')).toBe('income')
    expect(docTypeToRequestFact('income_support_doc')).toBe('income')
  })

  it('places every document type the api can store, and every one is accounted for', () => {
    for (const [docType, fact] of Object.entries(DOC_TYPE_FACT)) {
      expect([docType, docTypeToFact(docType)]).toEqual([docType, fact])
    }
    // A type the table forgot would otherwise read 'other' and look deliberate.
    expect(Object.keys(DOC_TYPE_FACT)).toHaveLength(19)
  })

  it('the student read-back folds `additional` into `other`, and renders every group it can answer', () => {
    // Her screen has five headings, not six (`scholarship.docs.section.*`). A group outside the
    // display order would not be merely unlabelled — the read-back iterates the ORDER, so the
    // document would vanish from the confirmation screen she is asked to check.
    for (const [docType, fact] of Object.entries(DOC_TYPE_FACT)) {
      const expected = fact === 'additional' ? 'other' : fact
      expect([docType, docTypeToStudentGroup(docType)]).toEqual([docType, expected])
      expect(STUDENT_DOC_GROUP_ORDER).toContain(docTypeToStudentGroup(docType))
    }
  })

  it('a document REQUEST folds `additional` into `other` too — the stored value stays one of five', () => {
    // `ResolutionItem.fact` is read back by the Action Centre (`item.fact === 'income'`) and by
    // `confirmTargetFor`; a sixth word would land in the database with nothing to read it.
    for (const [docType, fact] of Object.entries(DOC_TYPE_FACT)) {
      const expected = fact === 'additional' ? 'other' : fact
      expect([docType, docTypeToRequestFact(docType)]).toEqual([docType, expected])
    }
  })

  it('an unknown doc_type is "other" everywhere, never an error', () => {
    // A payload from a future api release must still show the student her own upload.
    expect(docTypeToFact('a_type_this_build_has_never_heard_of')).toBe('other')
    expect(docTypeToStudentGroup('a_type_this_build_has_never_heard_of')).toBe('other')
    expect(docTypeToRequestFact('a_type_this_build_has_never_heard_of')).toBe('other')
  })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// W-D — the student's green cue, and the arm it does not have
// ════════════════════════════════════════════════════════════════════════════════════════════
/**
 * ⚠ W7 HAS LEFT THIS FILE, because it is FIXED and no longer a drift to pin. The student's cue
 * required the supporting letter to be TAGGED to the earner while the api and the cockpit accept
 * it untagged; it now accepts an untagged letter (and requires the letter to have READ) exactly
 * as `income_engine.has_income_support_doc` does. What a student SEES is asserted where it can be
 * seen — `src/components/ScholarshipDocuments.test.tsx`, "the per-earner income tick counts what
 * the server counts", which mounts the tab and reads the green cue rather than the source.
 *
 * W6 stays, and it is now pinned as CORRECT rather than as a defect: see the comment inside it.
 */
describe('W-D memberIncomeShown — the student side', () => {
  it('W6 — the cue has THREE arms and no STR arm, and the owner says that is right', () => {
    // The original H8 finding called this drift: `member_income_evidenced`'s fourth arm is
    // `str_not_breached(application)`, which is ROUTE-AGNOSTIC (api twin
    // TestEachWayAlone.test_way4_non_breached_household_str — a SALARY-route household whose gate
    // clears on the STR alone), so a salary-route student holding a genuine STR is accepted by the
    // server while her Documents tab still asks for a payslip.
    //
    // ⚠ THE OWNER SETTLED IT THE OTHER WAY, 2026-09-19 (docs/decisions.md). An STR is evidence
    // about the HOUSEHOLD: it clears the gate and predicts green, and the working adults' income
    // proofs are ADDITIONAL to it, never replaced by it. So a household STR must NOT turn an
    // individual EARNER's tick green. The WEB is the side that matches the owner; the api's
    // fourth arm is a gate shortcut wearing a per-member name, and its docstring now says so.
    // DO NOT "fix" this by adding an STR arm. The disagreement is deliberate and this pins it.
    //
    // ⚠ SOURCE READ, and the reason is unchanged: `memberIncomeShown` is a closure inside a
    // ~1,960-line component with no export. It asserts the three arms are these three and that no
    // fourth appears. The rendered half — a household STR and nothing else leaves the earner
    // un-ticked — is in `ScholarshipDocuments.test.tsx`.
    const src = readFileSync(
      join(WEB_ROOT, 'src/components/ScholarshipDocuments.tsx'), 'utf8')
    expect(src).toContain('const memberIncomeShown = (m: WorkingMember): boolean =>')
    const start = src.indexOf('const memberIncomeShown')
    const body = src.slice(start, src.indexOf('const salaryComplete', start))
    expect(body).toContain("slotVerified('salary_slip', m)")
    expect(body).toContain("slotVerified('epf', m)")
    expect(body).toContain("d.doc_type === 'income_support_doc'")
    expect(body).not.toContain('str')          // ← no fourth arm, on either spelling
  })
})
