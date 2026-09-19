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
 *   W-C  `officerCockpit.docTypeToFact` (via `groupDocumentsByFact`) — which fact section a
 *        document is filed under. TWO further copies of this map exist and this file pins the gap.
 *   W-D  `ScholarshipDocuments.memberIncomeShown` — the STUDENT's green cue. Not exported (it is a
 *        closure inside the component), so it is characterised here by the api answer it claims to
 *        mirror plus a source-read pin; see the block at the foot of this file.
 *
 * The api answers quoted below are not guesses: each is the value asserted by the named test in
 * `test_income_evidence_homes.py`, which runs against the real engine.
 */
import { readFileSync } from 'fs'
import { join } from 'path'

import { groupDocumentsByFact, incomeSubSections } from '@/lib/officerCockpit'
import { incomeRequirements, salaryMemberBlocks, workingMembers } from '@/lib/incomeWizard'
import type { AdminApplicantDocument } from '@/lib/admin-api'

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

const SALARY_FATHER = { income_route: 'salary', income_earner: '', income_working_members: ['father'] }

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

  it('H8-FINDING (W2): a not_salary photo fills the officer slot that the gate refuses', () => {
    // api twin: TestNearMisses.test_not_salary_photo_in_the_payslip_slot_is_not_evidence —
    // `usable_salary_slip` refuses it (the #47 fix) and the gate emits
    // `income_evidence_missing:father`. The cockpit asks only `find('salary_slip', m)`, which is
    // PRESENCE. So the officer's panel shows the father's income evidence as satisfied, with no
    // Missing row, about a household the submission gate is holding shut.
    // Real student: application 73 — a MyKad photographed into the payslip slot.
    const rows = salaryRows(SALARY_FATHER, [
      doc({ id: 7, doc_type: 'salary_slip', household_member: 'father',
            authenticity: { status: 'not_salary', reason: 'reads as a MyKad' } })])
    expect(rows[0]).toEqual(['salary_slip', 'father', 7])      // ← no Missing row
  })

  it('H8-FINDING (W3): an EPF that reads nothing fills the officer slot that the gate refuses', () => {
    // api twin: TestNearMisses.test_unreadable_epf_is_not_evidence — `_member_has_epf_value`
    // requires a derivable monthly figure (owner 2026-07-25: "a readable EPF"), so the gate
    // blocks. The cockpit asks only `find('epf', m)`.
    const rows = salaryRows(SALARY_FATHER, [
      doc({ id: 8, doc_type: 'epf', household_member: 'father' })])
    expect(rows[0]).toEqual(['epf', 'father', 8])
  })

  it('H8-FINDING (W4): a support letter fills the slot with NO declared amount and NO read', () => {
    // api twin: TestNearMisses.test_letter_without_a_declared_amount_is_not_evidence (served
    // False) and `has_income_support_doc`, which additionally requires the letter to have READ
    // (`student_verdict == 'ok'` — the V1 finding #2 fix, so a blank image cannot "prove" a wage).
    // The cockpit requires neither. A student who uploads a blank letter and declares nothing
    // therefore sees her submission blocked while the officer's panel shows her income evidenced.
    const rows = salaryRows(SALARY_FATHER, [
      doc({ id: 9, doc_type: 'income_support_doc', household_member: 'father' })])
    expect(rows[0]).toEqual(['income_support_doc', 'father', 9])
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
// W-C — WHICH FACT a document is filed under, and the two copies that were never updated
// ════════════════════════════════════════════════════════════════════════════════════════════
describe('W-C the fact grouping — one rule, three copies', () => {
  it('the cockpit files the support letter under income (the 2026-09-07 fix)', () => {
    const groups = groupDocumentsByFact([doc({ id: 1, doc_type: 'income_support_doc' })])
    expect(groups.income).toHaveLength(1)
    expect(groups.other).toHaveLength(0)
  })

  it('H8-FINDING (W5): two further copies of that map still leave the letter out', () => {
    // TD-235 incident 2 was fixed in `officerCockpit.docTypeToFact` and NOWHERE ELSE. Two more
    // maps spell the same rule and neither gained the fourth way:
    //
    //   `src/app/admin/scholarship/[id]/view.tsx`      → DOC_FACT      (stamps a doc REQUEST's fact)
    //   `src/components/ScholarshipReview.tsx`         → DOC_CATEGORY  (the student's read-back)
    //
    // The second is LIVE and student-facing: `DOC_CATEGORY[d.doc_type] || 'other'` puts the one
    // document that proves her family's income under "Other" on the confirmation screen she reads
    // after giving consent. Real student: Janani — the same letter, the same word, the same
    // mistake, one component away from where it was corrected.
    // The first is LATENT: `view.tsx`'s REQUEST_CATEGORIES offers no `income_support_doc` request,
    // so no ticket can reach that line today — it becomes live the moment one is added.
    //
    // ⚠ This is a SOURCE READ because both maps are module-private consts with no export and no
    // seam. It pins the gap so it cannot widen silently; it is not a substitute for the rendered
    // test that should exist once the owner rules on the finding.
    const cockpit = readFileSync(join(WEB_ROOT, 'src/lib/officerCockpit.ts'), 'utf8')
    const view = readFileSync(
      join(WEB_ROOT, 'src/app/admin/scholarship/[id]/view.tsx'), 'utf8')
    const review = readFileSync(join(WEB_ROOT, 'src/components/ScholarshipReview.tsx'), 'utf8')

    // The scan can only mean anything if the maps are still where it looks — assert that first,
    // or a rename turns this test into a no-op that passes for ever.
    expect(cockpit).toContain('function docTypeToFact')
    expect(view).toContain('const DOC_FACT: Record<string, string>')
    expect(review).toContain('const DOC_CATEGORY: Record<string, string>')

    const factMap = (src: string, name: string) => {
      const start = src.indexOf(name)
      return src.slice(start, src.indexOf('}', start))
    }
    expect(cockpit).toContain("case 'income_support_doc':")

    const viewMap = factMap(view, 'const DOC_FACT: Record<string, string>')
    const reviewMap = factMap(review, 'const DOC_CATEGORY: Record<string, string>')
    // ⚠ A negative assertion over a slice is worthless until the slice is proved to hold the
    // thing it is supposed to be missing FROM. Each map must really carry the income group.
    expect(viewMap).toContain("salary_slip: 'income'")
    expect(reviewMap).toContain("salary_slip: 'income'")
    expect(viewMap).not.toContain('income_support_doc')
    expect(reviewMap).not.toContain('income_support_doc')
  })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// W-D — the student's green cue, and the arm it does not have
// ════════════════════════════════════════════════════════════════════════════════════════════
describe('W-D memberIncomeShown — the student side', () => {
  it('H8-FINDING (W6): it claims to mirror the api rule and is missing the STR arm', () => {
    // `ScholarshipDocuments.tsx` says, above `memberIncomeShown`:
    //   "mirrors income_engine.member_income_evidenced … a salary slip, an EPF, or a declared
    //    amount + a supporting letter. (STR would satisfy too, but an STR household is on the STR
    //    route, not here.)"
    // The parenthesis is the assumption that fails. `member_income_evidenced`'s fourth arm is
    // `str_not_breached(application)`, which is ROUTE-AGNOSTIC — pinned by the api twin
    // TestEachWayAlone.test_way4_non_breached_household_str, whose household is on the SALARY
    // route and whose gate clears on the STR alone. `income_doc_blockers` honours it too
    // (`household_str_status` short-circuits the salary branch).
    // So a salary-route student holding a genuine STR: the server has already decided her income
    // is shown and will let her submit, while her own Documents tab keeps the income block open
    // and un-green, asking for a payslip. Real student: #63 and #116 — both salary-route,
    // both holding a real STR.
    //
    // ⚠ SOURCE READ, for the same reason as W5: `memberIncomeShown` is a closure inside a 1,942-
    // line component with no export. The assertion is that the three arms are these three and
    // that no STR arm exists.
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

  it('H8-FINDING (W7): the student side requires the letter TAGGED; the api accepts untagged', () => {
    // api: `has_income_support_doc` filters `household_member__in=[member, '']` — "one family-level
    // supporting letter is enough under the flexible-evidence rule", and an Action-Centre upload
    // routinely lands untagged. The cockpit agrees (see W-B's untagged test). The STUDENT's cue
    // does not: `(d.household_member || '') === m`. So after she answers an officer's request for
    // a supporting letter, the server counts it, the officer sees it, and her own screen does not.
    const src = readFileSync(
      join(WEB_ROOT, 'src/components/ScholarshipDocuments.tsx'), 'utf8')
    const start = src.indexOf('const memberIncomeShown')
    const body = src.slice(start, src.indexOf('const salaryComplete', start))
    expect(body).toContain("(d.household_member || '') === m")
  })
})
