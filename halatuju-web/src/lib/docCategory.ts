/**
 * WHICH FACT A DOCUMENT BELONGS TO — one map, read by every screen that groups documents.
 *
 * **Why this file exists.** The same rule — "a payslip is income, an offer letter is pathway" —
 * was spelled out THREE times: `officerCockpit.docTypeToFact`, `view.tsx`'s `DOC_FACT` (which
 * stamps a document REQUEST's fact) and `ScholarshipReview.tsx`'s `DOC_CATEGORY` (the student's
 * post-consent read-back). Only the first was corrected on 2026-09-07 when the income-support
 * letter became income evidence, so the one document proving an informal earner's wage was still
 * filed under "Other" on the student's own confirmation screen (TD-235 incident 2, TD-262 / W5).
 * A rule with three homes gets fixed in one of them. This is the one home.
 *
 * **THE TWO VOCABULARIES ARE REAL, AND ARE ADAPTED HERE — not forked.** The officer's drawer has
 * six buckets; the student's read-back has five (there is no "Additional documents" heading on
 * her screen, so `additional` folds into `other`); a document REQUEST's `fact` is stored on a
 * `ResolutionItem` and read back by the Action Centre, which knows only the four verdict facts
 * plus `other` — so `additional` folds there too. Each fold is one function with its reason
 * written at it, so a difference is a decision somebody made rather than a map somebody forgot.
 *
 * ⚠ AN UNKNOWN TYPE IS `other`, NEVER AN ERROR. A payload from a future api release may carry a
 * doc_type this build has never heard of; a document the student really uploaded must still
 * appear on her screen, in the bucket for "everything else".
 */

/** The officer cockpit's six document buckets. */
export type DocFact = 'identity' | 'academic' | 'pathway' | 'income' | 'additional' | 'other'

/** The student read-back's five. No `additional`: her screen has no such heading. */
export type StudentDocGroup = 'identity' | 'academic' | 'pathway' | 'income' | 'other'

/**
 * Every value of `ApplicantDocument.DOC_TYPES` (`halatuju_api/apps/scholarship/models.py`)
 * appears below exactly once, and nothing else does. Pinned by
 * `src/lib/__tests__/incomeEvidenceHomes.test.ts` (W-C), which walks the whole list.
 *
 * The groupings, and the ones that are not obvious:
 *   * **The parent/guardian IC sits with INCOME.** The income documents (STR / salary slip / EPF)
 *     are issued in a parent's name, and the parent IC is what confirms that earner's identity.
 *   * **The relationship documents too** (birth certificate, guardianship letter): they link that
 *     earner to the student, so they belong to the income cluster.
 *   * **Utility bills** lend credibility to the income claim (the cockpit draws them in their own
 *     UTILITY sub-section).
 *   * ⚠ **THE SUPPORT LETTER IS INCOME EVIDENCE, NOT AN EXTRA — DO NOT MOVE IT BACK TO `other`.**
 *     It was filed under `other` until 2026-09-07 beneath a comment calling it a
 *     "reviewer-requested extra". That was true when it was written and stopped being true on
 *     2026-07-25, when `income_engine.member_income_evidenced` made a DECLARED amount backed by
 *     this letter one of the ways a family may prove what it earns. An informally-employed parent
 *     has no payslip and no EPF — the letter IS their income document, and filing it in the junk
 *     drawer hid the only evidence there was while the panel above it printed the salary slip as
 *     "Missing" in red. Found on application 144 (BrightPath #21).
 *   * **`additional`** is supporting context the student attaches to her case, not a verification
 *     fact: the school-leaving certificate, the statement of intent, the photo.
 *   * **`other`** is the catch-all — a reviewer-requested extra, a bank/reference document.
 */
const DOC_FACT_BY_TYPE: Record<string, DocFact> = {
  ic: 'identity',
  // Academic = the SPM slip AND the continuing-student current-CGPA slip.
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

/** Which verification-fact section of the officer's document drawer a doc_type belongs to. */
export function docTypeToFact(docType: string): DocFact {
  return DOC_FACT_BY_TYPE[docType] ?? 'other'
}

/**
 * The student read-back's group for a doc_type.
 *
 * ⚠ `additional` FOLDS INTO `other`, deliberately. `ScholarshipReview` renders one heading per
 * group from `scholarship.docs.section.<group>.title`, and there are five of those — the student
 * screen calls its last bucket "Additional documents" and puts every extra in it. A group with no
 * heading would not merely be unlabelled: the read-back iterates the ORDER below, so a document
 * in an unlisted group would silently vanish from the confirmation screen she is asked to check.
 */
export function docTypeToStudentGroup(docType: string): StudentDocGroup {
  const fact = docTypeToFact(docType)
  return fact === 'additional' ? 'other' : fact
}

/**
 * Display order for the student read-back: Identity → Results → Pathway → Income → Other, the
 * order the rest of her application runs in. Exported beside the fold above so the two cannot
 * drift apart — `docTypeToStudentGroup` may only ever answer a group that appears here.
 */
export const STUDENT_DOC_GROUP_ORDER: readonly StudentDocGroup[] = [
  'identity', 'academic', 'pathway', 'income', 'other',
]

/**
 * The `fact` stamped on a document REQUEST (`ResolutionItem.fact`) raised from the cockpit.
 *
 * ⚠ `additional` FOLDS INTO `other` here too, and for a different reason: this value is STORED on
 * the ticket and read back by consumers that know only the four verdict facts. `ActionCentre`
 * branches on `item.fact === 'income'`, `actionCentre.confirmTargetFor` routes the student by
 * substring, and the cockpit prints the raw value as a badge. Introducing a fifth word here would
 * write a value into the database that nothing downstream has copy or behaviour for.
 */
export function docTypeToRequestFact(docType: string): string {
  const fact = docTypeToFact(docType)
  return fact === 'additional' ? 'other' : fact
}
