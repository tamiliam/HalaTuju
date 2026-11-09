/**
 * Officer cockpit — the facts each document establishes, and its pill.
 *
 * One of five modules `officerCockpit.ts` was split into (audit A3.3, structure only — every line
 * below is the line it was). `officerCockpit.ts` re-exports all five, so `@/lib/officerCockpit`
 * still serves every importer.
 */

import { higherResultsFacts, slipHigherFacts } from '@/lib/higherResultsFacts'
import { offerFacts } from '@/lib/offerFacts'
import type { AdminApplicantDocument } from '@/lib/admin-api'

// ── Per-document verification facts (Sprint 2 redesign) ──────────────────────
// Each document shows the LABELS of the facts IT provides, coloured by sub-verdict —
// only what the document can establish. The relationship is "movable": it sits on a
// father/sibling IC (shared student-IC patronymic), on the BIRTH CERTIFICATE for a
// mother, and on the GUARDIANSHIP LETTER for a guardian — never on a mother's/guardian's
// IC. The per-fact checks (academic_check, income_ic_check, str_check, …) already arrive
// on the admin response (documents are serialised by ApplicantDocumentSerializer), so we
// read them directly — one source of truth, no parallel re-derivation.

export type FactStatus = 'verified' | 'partial' | 'not' | 'unknown'

export interface DocumentFactLabel {
  /** i18n key suffix under admin.scholarship.docsDrawer.fact.* */
  key: string
  status: FactStatus
}

/** Map the assorted check-status enums onto a single fact tone. */
function factStatus(s: string | undefined | null): FactStatus {
  switch (s) {
    case 'match': case 'found': case 'ok': case 'current':
      return 'verified'
    // `check_name` (#19): the names differ but the IC NUMBER matches exactly — amber, because the
    // number is the stronger evidence and a person should read the row, not a red that tells a
    // student to fetch a corrected certificate she cannot get.
    case 'partial': case 'uncertain': case 'pending': case 'stale': case 'unconfirmed': case 'check': case 'check_near':
    // `check_one` (#23): we held only ONE of the name/number pair, so only half the row was
    // checked. Green would claim a corroboration we do not have.
    case 'check_name': case 'check_one':
      return 'partial'
    case 'mismatch': case 'unreadable': case 'not_found': case 'rejected':
      return 'not'
    // 'not_compared' (request #62 review 2): no SPM prereq, so nothing was compared — grey, never amber
    default:                       // '', 'no_ref', 'unknown', 'not_compared', undefined
      return 'unknown'
  }
}

/**
 * STR currency state → doc-chip tone (str-proof-spec.md): a CURRENT approved STR is green; a
 * REJECTED (Ditolak) or WRONG_TYPE (a non-STR — payslip / SARA / SALINAN — in the STR slot) is
 * red; everything in between (unconfirmed = approved-but-undated, stale, unreadable/cropped) is
 * amber "confirm". NB the doc chip has no blue — 🔵 Probable is a verdict-TILE concept (the income
 * tile derives it from the review state + green evidence), not a per-document chip.
 */
function strCurrencyFactStatus(s: string | undefined | null): FactStatus {
  // The Current chip is the OPTIONAL variable — the cycle DATE only (approval lives on the Status
  // chip). Dated this cycle → green; a prior-year date → amber (a real concern); no date / can't
  // tell / not-an-STR → grey "we don't know" (its absence is not a fault).
  switch (s) {
    case 'current': return 'verified'
    case 'stale': return 'partial'
    case 'future': return 'partial'   // TD-403: a LATER year's page — not this year's proof
    default: return 'unknown'   // unconfirmed / unreadable / rejected / wrong_type → date unknown or n/a
  }
}

/**
 * Tone for the STR APPROVAL status chip — the third required STR variable (after recipient
 * name + IC), distinct from the currency/date dimension above. Was it approved (Lulus)?
 *   current / unconfirmed → carry an approved status → green (Lulus).
 *   stale / future (another year's page, TD-403) → grey — that year's status says nothing here.
 *   rejected (Ditolak) / wrong_type (not an STR at all) → red — no valid approval.
 *   unreadable (cropped page, status line not visible) → amber — couldn't read it, NOT a
 *     "not approved" (don't brand a cropped upload as rejected).
 */
function strStatusFactStatus(s: string | undefined | null): FactStatus {
  switch (s) {
    // TD-403 review: 'stale' is any EARLIER year's page, read status or not, so it no longer
    // implies Lulus — grey "we don't know", like 'future'; the Current chip carries the amber.
    case 'current': case 'unconfirmed': return 'verified'
    case 'rejected': case 'wrong_type': return 'not'
    case 'unreadable': return 'partial'
    default: return 'unknown'
  }
}

/**
 * Utility-bill recency → a THREE-tier traffic light on the officer chip (owner 2026-07-10), from
 * the backend `_utility_currency`:
 *   current (≤3 months)  → green  "Current"
 *   ageing  (3–6 months) → amber  "Ageing"   (accepted, not re-asked — the officer eyeballs it)
 *   stale   (>6 months)  → red    "Outdated"  (past the accept window → re-asked)
 *   unknown (no date)    → grey   "Current"   (recency can't be judged)
 * The LABEL changes with the tier so a red chip never reads the contradictory word "Current".
 */
function utilityCurrencyFact(s: string | undefined | null): DocumentFactLabel {
  switch (s) {
    case 'current': return { key: 'current', status: 'verified' }
    case 'ageing': return { key: 'ageing', status: 'partial' }
    case 'stale': return { key: 'stale', status: 'not' }
    default: return { key: 'current', status: 'unknown' }
  }
}

/**
 * Tone for a utility-bill ADDRESS check.
 *
 * The MATCHING is entirely the server's — a weighted matcher plus the officer flag — and it
 * arrives here as one word in `address_status`. Nothing of that logic is repeated below; this is
 * only how the screen COLOURS the word it was given: only a genuine 'mismatch' (a different home)
 * is red; 'unconfirmed'/'unreadable' (and the legacy 'not_found') mean "couldn't confirm" — amber,
 * eyeball at interview, never a hard miss; anything unrecognised falls to grey rather than
 * inventing a verdict.
 */
function addressFactStatus(s: string | undefined | null): FactStatus {
  switch (s) {
    case 'found': return 'verified'
    case 'mismatch': return 'not'
    case 'unconfirmed': case 'unreadable': case 'not_found': return 'partial'
    default: return 'unknown'      // '' — never run
  }
}

const _PATRONYMIC_MEMBER = new Set(['father', 'brother', 'sister'])

/**
 * Tone for the combined-utility "Reasonable" fact. A soft, noisy B40 proxy, so it never
 * shows red and only flags amber on genuinely HIGH consumption (> RM60/head — an
 * officer/interview signal). A normal household is green; one bill / no data is grey.
 */
function reasonableStatus(s: string): FactStatus {
  if (s === 'reasonable') return 'verified'
  if (s === 'high') return 'partial'
  return 'unknown'                       // 'partial' (one bill) + 'unknown' (no data) → grey
}

// A genuineness verdict that isn't 'genuine' → its own fact for the document. Two distinct tones
// (owner 2026-07-07): a `not_<type>` (the scorer says it isn't that KIND of document at all — e.g.
// an EPF filed as a salary slip) is a RED 'wrongType' — the wrong/"fake" document, its read values
// are meaningless. A `suspect` (thin fingerprints, usually a cropped page) is AMBER 'genuine' — "we
// aren't sure it's genuine"; the read VALUES still stand. null when no signal / genuine.
function genuinenessFact(doc: AdminApplicantDocument): DocumentFactLabel | null {
  const s = doc.authenticity?.status
  if (!s || s === 'genuine' || s === 'likely_genuine') return null
  if (s === 'final_owed') return { key: 'finalOwed', status: 'unknown' }   // M4b SF2: grey, never a doubt
  return s.startsWith('not_')
    ? { key: 'wrongType', status: 'not' }      // wrong document / fake → RED, caps its reads
    : { key: 'genuine', status: 'partial' }    // suspect → AMBER "unsure", does NOT cap the reads
}

// Only a WRONG-TYPE genuineness verdict (red) discredits the values read off a document — a merely
// SUSPECT (amber) one does not (a cropped-but-real slip still read the right name/grades). So the
// content facts are capped red only when the genuineness fact is itself red.
function genuinenessCaps(gf: DocumentFactLabel | null): boolean {
  return gf?.status === 'not'
}

/**
 * The coloured fact-labels for a document — only the facts that document provides.
 * Returns [] when the relevant check hasn't run (the row then renders as "unread").
 */
export function documentFacts(doc: AdminApplicantDocument): DocumentFactLabel[] {
  const dt = doc.doc_type
  // Genuineness is ONE fact of its own, computed once for every scored doc type. Two tones (owner
  // 2026-07-07): a WRONG-TYPE (`not_<type>`, red) discredits the reads (they came off the wrong
  // document — e.g. an EPF in the IC slot) so it CAPS them red; a merely SUSPECT (amber) upload —
  // usually a cropped page — does NOT cap them, so the Name/IC/etc. keep their real match/read
  // status and the amber Genuine chip says only "we aren't sure it's genuine".
  const gf = genuinenessFact(doc)
  const cap = genuinenessCaps(gf)
  if (dt === 'ic') {
    const nm: FactStatus = cap ? 'not' : factStatus(doc.vision_name_verdict)
    const icn: FactStatus = cap ? 'not' : factStatus(doc.vision_nric_verdict)
    const facts: DocumentFactLabel[] = [{ key: 'name', status: nm }, { key: 'ic_no', status: icn }]
    if (gf) facts.push(gf)
    return facts
  }
  if (dt === 'parent_ic') {
    const c = doc.income_ic_check
    if (!c) return []
    // The earner IC PROVIDES Name + IC No (legible = verified) — capped red only when genuineness
    // says it's the WRONG document (a not_ic upload). Relationship (patronymic) only for a father/
    // elder-sibling; mother/guardian prove it via the BC / guardianship letter.
    const read: FactStatus = cap ? 'not' : (c.readable ? 'verified' : 'not')
    const facts: DocumentFactLabel[] = [
      { key: 'name', status: read },
      { key: 'ic_no', status: read },
    ]
    if (gf) {
      facts.push(gf)
    } else if (c.wrong_card) {
      // The IC-number chain verified the earner from the BC + income proof, but the card in THIS
      // slot is a different family member's — a soft caveat (amber), never a block.
      facts.push({ key: 'wrong_card', status: 'partial' })
    } else if (_PATRONYMIC_MEMBER.has(c.member)) {
      facts.push({ key: 'relationship', status: factStatus(c.name_status) })
    }
    return facts
  }
  if (dt === 'results_slip') {
    const c = doc.academic_check
    if (!c) return []
    // Name / Subjects / Results show their REAL read+match status: green = matches what was entered,
    // red = a positive mismatch, grey = missing/not read. Genuineness is a SEPARATE fact: a
    // wrong-type (red) doc discredits the reads (they came off the wrong document) so it caps them;
    // a merely SUSPECT (amber) slip — usually a cropped footer — does NOT cap them, so the reviewer
    // sees "the values are here and match, but we're not certain the slip is genuine".
    const st = (v: string | undefined | null): FactStatus => (cap ? 'not' : factStatus(v))
    const facts: DocumentFactLabel[] = c.higher_kind ? slipHigherFacts(c, st) : [   // S4 (#43)
      { key: 'name', status: st(c.name) },
      { key: 'subjects', status: st(c.subjects) },
      { key: 'results', status: st(c.results) },
    ]
    if (gf) facts.push(gf)
    return facts
  }
  if (dt === 'higher_results') return higherResultsFacts(doc.higher_check, factStatus, gf)   // S3b; + Genuine chip (STPM S3)
  if (dt === 'offer_letter') return offerFacts(doc, factStatus)   // offer exact-read S6: its own leaf
  if (dt === 'str') {
    const c = doc.str_check
    if (!c) return gf ? [gf] : []
    // The three REQUIRED STR variables — recipient name, IC, and approval Status (Lulus) — then
    // Current (the date/cycle dimension). Genuineness cap: only a WRONG-TYPE (red) doc (a SALINAN,
    // a SARA letter, or the wrong document entirely) discredits these reads → red them all. A merely
    // SUSPECT (amber) STR does not — its chips keep their real status; the amber Genuine fact stands
    // alongside. (Currency vs approval stays in the Status/Current chips.)
    const facts: DocumentFactLabel[] = [
      { key: 'recipient', status: cap ? 'not' : factStatus(c.name_status) },
      { key: 'ic_no', status: cap ? 'not' : factStatus(c.nric_status) },
      { key: 'status', status: cap ? 'not' : strStatusFactStatus(c.current_status) },
      { key: 'current', status: cap ? 'not' : strCurrencyFactStatus(c.current_status) },
    ]
    if (gf) facts.push(gf)
    return facts
  }
  if (dt === 'salary_slip' || dt === 'epf') {
    const c = doc.income_proof_check
    // Genuineness cap: only a WRONG-TYPE (red) doc — an EPF signature-scored `not_epf`, or a salary
    // slip the light wrong-type backstop reads as another document (`not_salary_slip`) — discredits
    // the earner reads (off the wrong paper), so red them. A merely SUSPECT (amber) one does not.
    if (!c) return gf ? [gf] : []
    const has = (k: string) => (c.points || []).some((p) => p.key === k && (p.value || '').trim())
    const facts: DocumentFactLabel[] = [{ key: 'name', status: cap ? 'not' : factStatus(c.name_status) }]
    // IC No: an EPF statement always carries the member's number; a salary slip only sometimes
    // (hide it there when absent). Same treatment the STR chip gives it — the number is the strong
    // earner key — and both read `nric` off the check object the server sent, not a rule of ours.
    // TD-220: red said "mismatch" and "not read" alike. Now: a number read and differing → the
    // mismatch chip; a slip that read nothing (unreadable / wrong_doc) → the unreadable chip; an
    // `incomplete` slip with no number → no IC chip (doc_match_verdict counts it unreadable; we don't).
    if ((c.nric || '').trim()) {
      const differs = !cap && c.nric_status === 'mismatch'
      facts.push({ key: differs ? 'ic_no_mismatch' : 'ic_no', status: cap ? 'not' : factStatus(c.nric_status) })
    } else if (!cap && ['unreadable', 'wrong_doc'].includes(doc.vision_fields?.student_verdict || '')) {
      facts.push({ key: 'ic_no_unreadable', status: 'not' })
    }
    if (dt === 'salary_slip') {
      // CONSISTENT chip set for every salary slip: Amount + Period always present, grey ('unknown')
      // when not read — never omitted, so two payslips don't show different numbers of chips.
      // TD-323: amber, never green, on a figure the engine refused (served `figure_refused`).
      facts.push(doc.figure_refused ? { key: 'amount_unusable', status: 'partial' }
        : { key: 'amount', status: (has('amount') || has('gross_income') || has('net_income')) ? 'verified' : 'unknown' })
      facts.push({ key: 'period', status: has('period') ? 'verified' : 'unknown' })
    } else {
      // EPF: surface what we already collect (the FE previously looked for a wrong key so NONE
      // showed). Contribution = the income figure; Balance = JUMLAH SIMPANAN; Date = statement
      // currency. Keys match income_engine.student_income_proof_check's EPF points.
      facts.push(doc.figure_refused ? { key: 'contribution_unusable', status: 'partial' }
        : { key: 'contribution', status: has('avgContribution') ? 'verified' : 'unknown' })
      facts.push({ key: 'balance', status: has('totalAccumulated') ? 'verified' : 'unknown' })
      facts.push({ key: 'current', status: has('statementDate') ? 'verified' : 'unknown' })
    }
    if (gf) facts.push(gf)
    return facts
  }
  if (dt === 'birth_certificate') {
    const c = doc.bc_check
    if (!c) return []
    // ⚠ NOTHING READ IS NOT NOTHING WRONG (#23). Every row of an unreadable certificate buckets
    // to `no_ref`, and three GREY chips read like an absent optional document — the same as one
    // that checked out. One AMBER chip instead, so the officer sees a document to chase.
    // Review F1: a wrong-type upload that also read nothing (a selfie) still carries its red chip.
    if (c.unreadable) return gf ? [{ key: 'unreadable', status: 'partial' }, gf] : [{ key: 'unreadable', status: 'partial' }]
    // TD-158: the same cap and Genuine chip every other scored type carries. A `not_birth_certificate`
    // (red) discredits the reads, so no green tick; a merely SUSPECT one keeps them beside an amber chip.
    const facts: DocumentFactLabel[] = [
      { key: 'child', status: cap ? 'not' : factStatus(c.child_status) },
      { key: 'mother', status: cap ? 'not' : factStatus(c.mother_status) },
      { key: 'father', status: cap ? 'not' : factStatus(c.father_status) },
    ]
    if (gf) facts.push(gf)
    return facts
  }
  if (dt === 'guardianship_letter') {
    const c = doc.guardianship_check
    if (!c) return []
    if (c.unreadable) return [{ key: 'unreadable', status: 'partial' }]
    return [
      { key: 'guardian', status: factStatus(c.guardian_status) },
      { key: 'ward', status: factStatus(c.ward_status) },
    ]
  }
  if (dt === 'semester_result') {
    // Owner 2026-07-05: read a semester slip for exactly three things — Name + IC No (matched
    // against the student: green on a match, red otherwise incl. not-found) and CGPA (green when a
    // cumulative figure is read, GREY when it's a semester-only slip — never red, never flagged).
    const c = doc.semester_check
    if (!c) return []   // not read yet → the row shows "Unread"
    const idMatch = (s: string): FactStatus => (s === 'match' || s === 'partial' ? 'verified' : 'not')
    return [
      { key: 'name', status: idMatch(c.name_status) },
      { key: 'ic_no', status: idMatch(c.nric_status) },
      { key: 'cgpa', status: (c.cgpa || '').trim() ? 'verified' : 'unknown' },
    ]
  }
  if (dt === 'school_leaving_cert') {
    // Owner 2026-07-15: School / Name / IC are MATCH chips against the student's own profile — green
    // match, amber partial, red mismatch, grey when we can't compare (factStatus). Behaviour is a
    // QUALITY chip off the conduct rating — green good (Baik/Terpuji/Cemerlang), amber middling
    // (Sederhana), RED poor (Kurang Memuaskan…), grey unread. The leadership notes (+ a school /
    // conduct value only when it's worth a second look) render below via schoolLeavingValues.
    const c = doc.school_leaving_check
    if (!c) return []   // not read yet → the row shows "Unread"
    const behaviour: FactStatus =
      c.kelakuan_status === 'good' ? 'verified'
        : c.kelakuan_status === 'concern' ? 'partial'
          : c.kelakuan_status === 'bad' ? 'not' : 'unknown'
    return [
      { key: 'school', status: factStatus(c.school_status) },
      { key: 'name', status: factStatus(c.name_status) },
      { key: 'ic_no', status: factStatus(c.nric_status) },
      { key: 'behaviour', status: behaviour },
    ]
  }
  if (dt === 'income_support_doc') {
    // V1: the declared-income supporting doc. It NAMES THE EARNER, not the student, so there
    // is no student name-match — the READ is the signal (a blank image can't prove a wage).
    // 'Evidence' = did it read as a real support document; 'Amount' when a figure was found.
    const c = doc.support_doc_check
    if (!c) return []
    const facts: DocumentFactLabel[] = [
      { key: 'evidence', status: c.read_status === 'read' ? 'verified' : 'not' },
    ]
    if ((c.amount || '').trim()) facts.push({ key: 'amount', status: 'verified' })
    return facts
  }
  if (dt === 'water_bill' || dt === 'electricity_bill') {
    const c = doc.utility_check
    // A WRONG-TYPE upload — caught SYMMETRICALLY in either slot: an electricity bill scored
    // `not_electricity_bill` (a water bill / MyKad / junk), OR a water bill scored `not_water_bill`
    // (an ELECTRICITY bill / MyKad / junk) — shows the red "Wrong type" chip like every other doc,
    // even if utility_check read some fields off the wrong document (those reads are then capped
    // red / dropped).
    if (!c) return gf ? [gf] : []
    // Address · Current · Reasonable always; Outstanding only when arrears > the charge
    // (a real hardship signal, shown green). 'current'/'stale'/'unknown' map through
    // factStatus directly (current→green, stale→amber, unknown→grey). Capped red when the
    // genuineness fact is wrong-type — the reads came off the wrong document.
    const facts: DocumentFactLabel[] = [
      { key: 'address', status: cap ? 'not' : addressFactStatus(c.address_status) },
      cap ? { key: 'current', status: 'not' } : utilityCurrencyFact(c.current_status),
      { key: 'reasonable', status: cap ? 'not' : reasonableStatus(c.reasonable_status) },
    ]
    if (!cap && c.outstanding_status === 'arrears') {
      facts.push({ key: 'outstanding', status: 'verified' })
    }
    if (gf) facts.push(gf)
    return facts
  }
  return gf ? [gf] : []
}

// ── The SPM year, on the merit score ─────────────────────────────────────────

export interface SpmExamYear {
  /** The four-digit year, read off the live results slip. Never blank (null is returned instead). */
  year: string
  /** Currency vs the intake: 'current' = the year we expect, 'off' = any other, '' = no cohort. */
  status: '' | 'current' | 'off'
}

/**
 * The SPM year that produced this merit score.
 *
 * ⚠ IT QUALIFIES THE MERIT SCORE, WHICH IS WHY IT BELONGS BESIDE IT rather than on a banner of its
 * own. The score is computed from the SPM grades, so the year those grades were sat is a property
 * of that number — "94.7" and "94.7 (SPM 2023)" are not the same claim.
 *
 * The engine has read this year and judged its currency for months. It surfaced only as a small
 * tinted chip inside the Documents drawer, fed nothing, and was reliably missed — one applicant in
 * four on the 2026 intake did not sit SPM the year before it (BrightPath request #12). The signal
 * was never absent; it was quiet, next to a loud verdict.
 *
 * ⚠ THIS FUNCTION DOES NOT KNOW THE QUALIFICATION, AND ITS CALLER MUST. An STPM student's merit
 * comes from STPM, so attaching an SPM year to it would state something false about where the
 * number came from — the same misattribution that once put an SPM slip's tick on STPM grades
 * (#132). The caller decides; this only reports what the slip says.
 *
 * Null when there is no live results slip or the slip carries no readable year — the merit score
 * then renders bare, exactly as it does today, and that silence is honest: it means we could not
 * read the year, not that the year is unremarkable.
 */
export function spmExamYear(documents: AdminApplicantDocument[] | undefined): SpmExamYear | null {
  const slip = (documents || []).find(
    (d) => d.doc_type === 'results_slip'
      && !d.superseded_at
      && !!(d.academic_check?.exam_year || '').trim(),
  )
  const check = slip?.academic_check
  if (!check) return null
  return { year: check.exam_year.trim(), status: check.exam_year_status || '' }
}

// ── Utility-bill key values (at-a-glance, so the reviewer needn't open the document) ─────────

export interface UtilityValue {
  /** i18n key suffix under admin.scholarship.docsDrawer.billValue.* */
  labelKey: string
  /** the display value, OR a valueKey (i18n) for a fixed word like "none" */
  value?: string
  valueKey?: string
}

function _formatRm(s: string): string {
  const t = (s || '').trim()
  if (!t) return t
  return /^rm/i.test(t) ? t.replace(/^rm\s*/i, 'RM') : `RM${t}`
}

function _arrearsAmount(s: string | undefined): number | null {
  const n = parseFloat((s || '').replace(/[^0-9.-]/g, ''))
  return Number.isFinite(n) ? n : null
}

/**
 * The KEY VALUES the AI read off a utility bill, for a compact at-a-glance line in the cockpit so
 * the reviewer gets the picture without opening the document (owner 2026-07-10): Amount (current
 * charge), Period (bill date, else billing period), Arrears. Reviewer-facing labels; empties are
 * skipped. Amount/arrears come from utility_check; period from vision_fields. (Account number is
 * deliberately NOT shown — not decision-relevant, owner 2026-07-10.)
 */
export function utilityBillValues(doc: AdminApplicantDocument): UtilityValue[] {
  const c = doc.utility_check
  if (!c) return []
  const f = (doc.vision_fields as { fields?: Record<string, string> } | null | undefined)?.fields ?? {}
  const out: UtilityValue[] = []
  const amount = (c.monthly_bill || '').trim()
  if (amount) out.push({ labelKey: 'amount', value: _formatRm(amount) })
  // Standardised 'MMM YYYY' from the backend (same date as the currency chip); raw string only as a
  // fallback when the date couldn't be parsed into a month.
  const period = (c.bill_month || f.bill_date || f.billing_period || '').trim()
  if (period) out.push({ labelKey: 'period', value: period })
  // Arrears: a real positive Tunggakan → the amount; the bill was read but shows none/credit → the
  // fixed word "none"; the bill wasn't read at all (no amount) → omit (don't claim "none").
  const arr = _arrearsAmount(c.unpaid_balance)
  if (arr !== null && arr > 0) out.push({ labelKey: 'arrears', value: _formatRm((c.unpaid_balance || '').trim()) })
  else if (amount) out.push({ labelKey: 'arrears', valueKey: 'none' })
  return out
}

/**
 * The school-leaving certificate's VALUES to show inline under its chips (owner 2026-07-15):
 * the school name, the conduct rating (kelakuan), and the co-curricular / leadership notes
 * (activities). labelKey maps to admin.scholarship.docsDrawer.certValue.*. Empty ones are omitted.
 */
export function schoolLeavingValues(doc: AdminApplicantDocument): UtilityValue[] {
  const c = doc.school_leaving_check
  if (!c) return []
  const out: UtilityValue[] = []
  // Owner 2026-07-15: the school + conduct VALUES are redundant with their (green) chips in the clean
  // case — show them ONLY when there's a discrepancy worth the officer's eye: a non-matching school,
  // or a middling/poor conduct. The leadership notes always show (they're not on any chip).
  if ((c.school || '').trim() && c.school_status !== 'match' && c.school_status !== 'no_ref') {
    out.push({ labelKey: 'school', value: c.school.trim() })
  }
  if ((c.kelakuan || '').trim() && (c.kelakuan_status === 'concern' || c.kelakuan_status === 'bad')) {
    out.push({ labelKey: 'behaviour', value: c.kelakuan.trim() })
  }
  if ((c.activities || '').trim()) out.push({ labelKey: 'notes', value: c.activities.trim() })
  return out
}

// ── Document pill (the row's aggregate badge) ────────────────────────────────

export type DocumentPill = 'verified' | 'check' | 'unread'

/**
 * The row's badge is the ROLL-UP of its fact colours:
 *   unread  — no fact could be assessed yet (the check hasn't run);
 *   verified— every assessable fact is verified;
 *   check   — at least one fact is partial or not-verified.
 * Deriving from documentFacts means the earner IC (parent_ic) is judged by its income
 * relationship check, not the student-identity verdict it never gets — which removes the
 * old "earner IC always Unread" bug.
 */
export function documentPill(doc: AdminApplicantDocument): DocumentPill {
  const facts = documentFacts(doc).filter((f) => f.status !== 'unknown')
  if (facts.length === 0) return 'unread'
  return facts.every((f) => f.status === 'verified') ? 'verified' : 'check'
}
