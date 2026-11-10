/**
 * Officer cockpit — income sub-sections, document icons and the in-cockpit viewer kind.
 *
 * One of five modules `officerCockpit.ts` was split into (audit A3.3, structure only — every line
 * below is the line it was). `officerCockpit.ts` re-exports all five, so `@/lib/officerCockpit`
 * still serves every importer.
 */

import type { AdminApplicantDocument } from '@/lib/admin-api'

// ── Income section layout (route + selection aware) ──────────────────────────
// A compulsory income document that isn't uploaded shows as a "Missing" placeholder, and the
// required slots are derived the same way the gate and the student wizard derive them
// (workingMembers + relationshipDocFor), so the cockpit can't disagree with what the student was
// actually asked for. The one function that builds them is `incomeSubSections`, below.
//
// (A second builder, `incomeDocLayout`, lived here until 2026-09-07 with no caller but its own
// tests. It was found while fixing the panel, having quietly stated a rule superseded in July —
// a fix applied to it alone would have passed every gate and changed nothing on screen.)

import { workingMembers, relationshipDocFor, MEMBER_ORDER, type WorkingMember } from '@/lib/incomeWizard'
import { answerFor, unusableReason, type IncomeShownMap, type IncomeShownReason } from '@/lib/incomeShown'

export interface IncomeSlot {
  docType: string
  member: string                       // '' for STR / untagged household docs
  doc: AdminApplicantDocument | null   // the uploaded doc, or null = missing → placeholder
  /** A served reason code (`income_shown.REASONS`) when this document was offered as the
   *  earner's income evidence and cannot carry it; '' otherwise. The row still SHOWS — the
   *  officer must see what the family sent — marked as not usable, with the red Missing row
   *  beside it. */
  unusable?: IncomeShownReason
}

interface IncomeAnswerSource {
  income_route?: string | null
  income_earner?: string | null
  income_working_members?: string[] | null
  /** TD-262 chunks 2+3 — the served per-earner answer. Absent on an old/cached payload, which
   *  falls back to the presence reading this panel used to do on its own. */
  income_shown?: IncomeShownMap | null
}

// ── Income sub-sections (STR ROUTE / SALARY ROUTE / UTILITY) ──────────────────────────
// The DOCUMENT drives the space, not the declared route (owner, 2026-07-04): the moment an
// STR-claiming doc exists, the STR cluster shows so the reviewer can eyeball it — currency /
// verification only colour the rows, never whether they appear. A household is not one route:
// an STR mother may also work; a father may earn a salary — so the box shows an STR cluster AND
// a salary cluster AND utilities as distinct sub-sections. Docs are placed by their RESOLVED
// member (stored tag, or the name on a blank-tagged doc matched to the roster). Visibility:
//   STR      — whenever an STR document exists (any route). Cluster = STR proof(s) + that
//              parent's IC + the applicant's BC (guardian letter for a guardian; none for a father).
//   SALARY   — the working members' docs (salary slip → IC → EPF). The IC is SKIPPED for the STR
//              parent (already shown under STR — the shared-IC rule).
//   UTILITY  — the uploaded water/electricity bills.
//   Any income doc not placed above falls into a SALARY catch-all — no doc is ever hidden.
export interface IncomeSubSections {
  str: IncomeSlot[] | null    // null → hide the STR sub-section entirely
  salary: IncomeSlot[]        // may be empty (then hidden by the renderer)
  utility: IncomeSlot[]       // may be empty (then hidden by the renderer)
}

export function incomeSubSections(app: IncomeAnswerSource, incomeDocs: AdminApplicantDocument[]): IncomeSubSections {
  const earner = app.income_earner || ''
  // Place a doc by its RESOLVED member: the stored tag, or (blank-tagged) the person resolved from
  // the name on the doc against the family roster (backend `resolved_member`). Falls back to ''.
  const memberOf = (d: AdminApplicantDocument) => d.resolved_member || d.household_member || ''
  const find = (dt: string, member: string) =>
    incomeDocs.find((d) => d.doc_type === dt && memberOf(d) === member) || null
  const used = new Set<number>()
  const mark = (slots: IncomeSlot[]) => slots.forEach((s) => { if (s.doc?.id != null) used.add(s.doc.id) })

  // UTILITY — the uploaded bills, electricity first.
  const utility: IncomeSlot[] = incomeDocs
    .filter((d) => d.doc_type === 'water_bill' || d.doc_type === 'electricity_bill')
    .sort((a, b) => (a.doc_type === 'electricity_bill' ? -1 : 1) - (b.doc_type === 'electricity_bill' ? -1 : 1))
    .map((d) => ({ docType: d.doc_type, member: memberOf(d), doc: d }))
  mark(utility)

  // STR ROUTE — shows whenever an STR-claiming doc exists. The STR parent = the STR route's earner,
  // else the member the STR is tagged/resolved to. Cluster: STR proof(s) → parent IC → applicant BC
  // (guardian letter for a guardian; none for a father earner).
  let str: IncomeSlot[] | null = null
  let strParent = ''
  const strDocs = incomeDocs.filter((d) => d.doc_type === 'str')
  if (strDocs.length > 0) {
    // The STR parent = whoever the STR is TAGGED/resolved to (the recipient), NOT the declared
    // income_earner — on the salary route they differ (#45: the father's STR, the mother the declared
    // earner). Keying off `earner` filed the WRONG parent's IC under STR ROUTE (mother's) and pushed
    // the real recipient's (father's) to SALARY. Prefer the STR's own member; earner is the fallback
    // (on the STR route the wizard tags the STR to the earner, so they agree there).
    strParent = memberOf(strDocs[0]) || earner || ''
    const s: IncomeSlot[] = strDocs.map((d) => ({ docType: 'str', member: memberOf(d) || strParent, doc: d }))
    s.push({ docType: 'parent_ic', member: strParent, doc: find('parent_ic', strParent) })
    const rel = relationshipDocFor(strParent)   // mother→BC, guardian→letter, father→none
    if (rel) s.push({ docType: rel, member: '', doc: find(rel, '') })
    mark(s)
    str = s
  }

  // SALARY ROUTE — the working members' docs: salary slip → IC → EPF, per the spec order. The IC
  // is SKIPPED for the STR parent (shared-IC: their IC is already under STR). Missing compulsory
  // slots render as "Missing" placeholders; EPF is present-only (additional).
  //
  // …EXCEPT on the STR route: an STR family's salary docs are SUPPORTIVE, not required (the STR is
  // the means-test). So we never nag for an absent salary-route doc with a red "Missing" placeholder
  // — the section shows only what's actually on file (good-to-have evidence). If an officer wants a
  // specific one, they raise a Check-2 request and it appears here once uploaded. On the SALARY route
  // those docs ARE the proof, so the compulsory placeholders stay. (owner 2026-07-05.)
  //
  // The member list is the UNION of the DECLARED working members and any member who ACTUALLY HAS an
  // earning doc on file (a salary_slip or EPF, by resolved member) — so a mixed household gets
  // structured Father/Mother groups even when the route is STR (which carries no working-member list)
  // or a working member wasn't declared. A member with only an IC is NOT pulled in this way (that's
  // usually the STR parent's IC, already under STR) — it would otherwise raise a false "Missing
  // salary" placeholder for a non-earner. (4a, owner 2026-07-05.)
  const memberSet = new Set<string>(
    workingMembers(app.income_working_members as WorkingMember[] | null) as string[])
  for (const d of incomeDocs) {
    if (d.doc_type === 'salary_slip' || d.doc_type === 'epf') {
      const m = memberOf(d)
      if (m) memberSet.add(m)
    }
  }
  const salaryMembers = Array.from(memberSet).sort((a, b) => {
    const ra = MEMBER_ORDER.indexOf(a as WorkingMember), rb = MEMBER_ORDER.indexOf(b as WorkingMember)
    return (ra < 0 ? 99 : ra) - (rb < 0 ? 99 : rb)
  })
  const salary: IncomeSlot[] = []
  // Salary docs are SUPPORTIVE (present-only, no compulsory "Missing" rows) whenever the STR is the
  // means-test — i.e. the declared STR route, OR a valid STR proof is on file that hasn't been
  // BREACHED. Owner principle (2026-07-05): a genuine approved STR proves B40, so the family need not
  // fall into full salary-route documentation regardless of the declared route (#63 was on the salary
  // route while holding a valid Lulus STR, so a route-only check wrongly demanded the mother's slip).
  // Check-2 may still SOFTLY ask about declared earners; it just isn't a hard requirement. A BREACHED
  // STR (rejected / wrong-type / not-genuine) drops the family into full salary docs, as before.
  const strNotBreached = strDocs.some((d) => {
    // compared as strings: the backend emits current_status values ('wrong_type', 'unreadable') and
    // authenticity states ('likely_genuine') that the narrower FE unions don't enumerate.
    const cs = String(d.str_check?.current_status || '')
    const auth = String(d.authenticity?.status || '')
    // TD-403 (2026-10-26): an earlier year's ('stale') or a later year's ('future') STR is not this
    // year's proof, so it no longer makes the salary documents supportive — as `str_not_breached`.
    if (!cs || cs === 'wrong_type' || cs === 'rejected' || cs === 'stale' || cs === 'future') return false
    if (auth && auth !== 'genuine' && auth !== 'likely_genuine') return false
    return true
  })
  const salaryRequired = (app.income_route || '') !== 'str' && !strNotBreached
  const pushSlot = (docType: string, member: string, doc: AdminApplicantDocument | null,
                    unusable: IncomeShownReason = '') => {
    if (doc || salaryRequired) salary.push({ docType, member, doc, unusable })
  }
  // ⚠ ONE INCOME SLOT PER EARNER, SATISFIED ANY ONE WAY — NOT A SALARY-SLIP SLOT.
  // This asked for `salary_slip` by name and rendered a red "Missing" when it was absent, which
  // stopped being the rule on 2026-07-25: `income_engine.member_income_evidenced` accepts a
  // payslip OR a readable EPF statement OR a declared amount backed by an `income_support_doc`.
  // An informally-employed parent has no payslip and no EPF, so the panel was demanding, in red,
  // a document the system does not require — application 144's mother, a self-employed trader
  // with a signed and endorsed income letter on file (BrightPath #21).
  // The slot names WHAT IS THERE, and says "income evidence" only when NOTHING is: at that point
  // any of the three would satisfy it, so naming one of them misstates what is being asked for.
  const claimedSupport = new Set<number>()
  const supportFor = (m: string) => {
    // Tagged to this member, else a household-level (untagged) letter — the backend tolerates
    // both. Claimed once, so two earners can never both rest on the same single letter.
    const own = find('income_support_doc', m)
    const shared = incomeDocs.find((d) => d.doc_type === 'income_support_doc' && !memberOf(d))
    const pick = own || (shared && !claimedSupport.has(shared.id) ? shared : null)
    if (pick) claimedSupport.add(pick.id)
    return pick || null
  }
  for (const m of salaryMembers) {
    const slip = find('salary_slip', m)
    const epfDoc = find('epf', m)
    const evidence = slip || epfDoc || supportFor(m)
    // ⚠ EVIDENCE IS THE SERVED ANSWER, NOT THE PRESENCE OF A FILE (TD-262, W2/W3/W4). A document
    // that cannot carry this earner's income is STILL LISTED — the officer must see what the
    // family sent, and why it does not count — and the red Missing row appears beside it. With no
    // served answer (an old or cached payload) `shown` degrades to the presence reading this panel
    // used to do on its own, so the panel never gets WORSE than it was.
    const answer = answerFor(app.income_shown, m)
    const shown = answer ? answer.shown : Boolean(evidence)
    if (evidence) pushSlot(evidence.doc_type, m, evidence, unusableReason(answer, evidence.id))
    if (!shown) pushSlot('income_evidence', m, null)
    if (m !== strParent) {
      pushSlot('parent_ic', m, find('parent_ic', m))
      // Relationship proof sits DIRECTLY BELOW the person's IC (guardian → guardianship letter,
      // mother → BC; father none). Skip the STR parent's (already under STR) and never duplicate a
      // single household doc.
      const rel = relationshipDocFor(m as WorkingMember)
      if (rel && !salary.some((s) => s.docType === rel && s.member === '')) {
        pushSlot(rel, '', find(rel, ''))
      }
    }
    // The EPF still shows as supporting evidence BELOW the IC — unless it was already used as
    // this member's income evidence above (no payslip), in which case showing it twice would
    // read as two documents.
    if (epfDoc && epfDoc !== evidence) {
      salary.push({ docType: 'epf', member: m, doc: epfDoc,
                    unusable: unusableReason(answer, epfDoc.id) })
    }
  }
  mark(salary)
  // Catch-all: EVERY income doc not already placed is appended here (known types ordered, others
  // last) — the invisible-document guard, so no uploaded income doc is ever dropped from view.
  const SALARY_TAIL = ['salary_slip', 'epf', 'parent_ic', 'birth_certificate', 'guardianship_letter']
  const rankTail = (dt: string) => { const i = SALARY_TAIL.indexOf(dt); return i < 0 ? 99 : i }
  const tail = incomeDocs
    .filter((d) => !used.has(d.id))
    .sort((a, b) => rankTail(a.doc_type) - rankTail(b.doc_type))
    .map((d) => ({ docType: d.doc_type, member: memberOf(d), doc: d }))
  salary.push(...tail)

  return { str, salary, utility }
}

// ── Document row presentation (cockpit Documents drawer) ─────────────────────────────
// A per-doc-TYPE emoji glyph (no icon library), so the icon carries meaning; the row tints it by verdict.
const DOC_ICON: Record<string, string> = {
  ic: '🪪', parent_ic: '🪪', results_slip: '🎓', higher_results: '🎓', offer_letter: '🏫',
  str: '💵', salary_slip: '🧾', epf: '🏦', income_support_doc: '✉️', water_bill: '💧',
  electricity_bill: '⚡', birth_certificate: '👶', guardianship_letter: '📜',
  statement_of_intent: '✍️', photo: '🖼️',
}

export function docIconFor(docType: string): string {
  return DOC_ICON[docType] || '📄'
}

// The household member an income doc belongs to, for the person-qualified label ("Mother's IC",
// "Father's salary slip"): its own tag, or — on the STR route, where the single earner's income
// docs may carry a legacy blank tag — the application's income_earner. '' when it can't be derived
// (label falls back to the generic type, e.g. "Earner's IC").
const _INCOME_EARNER_DOCS = new Set(['parent_ic', 'str', 'salary_slip', 'epf'])
export function earnerMemberFor(docType: string, householdMember: string, route: string, earner: string): string {
  if (householdMember) return householdMember
  if (route === 'str' && _INCOME_EARNER_DOCS.has(docType)) return earner || ''
  return ''
}

// How to render a document in the in-cockpit viewer (Option B): images via <img>, PDFs via
// <iframe>; HEIC/HEIF can't render in any browser → 'unsupported' (the viewer offers the
// original + we convert HEIC server-side on upload). Decided by content-type, filename as backup.
export function viewerKind(contentType: string, filename: string): 'image' | 'pdf' | 'unsupported' {
  const ct = (contentType || '').toLowerCase()
  const fn = (filename || '').toLowerCase()
  if (ct === 'application/pdf' || fn.endsWith('.pdf')) return 'pdf'
  if (ct.includes('heic') || ct.includes('heif') || fn.endsWith('.heic') || fn.endsWith('.heif')) return 'unsupported'
  if (ct.startsWith('image/') || /\.(jpe?g|png|gif|webp|bmp)$/.test(fn)) return 'image'
  return 'unsupported'
}
