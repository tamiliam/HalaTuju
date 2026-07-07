/**
 * Pure logic for the Officer Review Cockpit (Sprint 5).
 *
 * All helpers are side-effect-free so they can be unit-tested in a plain
 * node env (no jsdom). The cockpit component consumes these; it never
 * re-implements them.
 */

import type { AdminVerdictFact, AdminVerdictItem, AdminApplicantDocument, VerdictMetrics } from '@/lib/admin-api'

// ── Verdict item i18n key ─────────────────────────────────────────────────────

// STR-not-current copy is per-status (decisive, no word-salad). The backend keeps a
// single item code `str_not_current` (resolution/help engines key off that literal),
// and tags the reason in params.status. The custom i18n `t` has NO ICU MessageFormat —
// only flat `{var}` interpolation — so an ICU `select` would render raw. Resolve to a
// flat per-status key here instead: str_not_current_{wrong_type,rejected,stale,
// unreadable,unconfirmed}. Default to 'unconfirmed' (the approved-but-dateless case).
export function verdictItemKey(it: AdminVerdictItem): string {
  if (it.code === 'str_not_current') {
    return `str_not_current_${String(it.params?.status || 'unconfirmed')}`
  }
  return it.code
}

// ── Fact tile tone ───────────────────────────────────────────────────────────

export type FactTileTone = 'green' | 'amber' | 'blue' | 'red'

// Evidence codes that are NOT a verified value — a self-declaration or a soft signal.
// "Probable" (blue) must rest on at least one real verified value, so a fact backed
// only by these (or by nothing) is "Unsure", not "Probable".
//
// PINNED to the backend: every code the verdict engine emits with a `# SOFT` marker
// MUST appear here (and nothing here should be un-marked there). The jest guard
// `__tests__/soft-evidence-drift.test.ts` reads verdict_engine.py and fails on any
// drift — the denylist had rotted (Phase-2B/2C soft codes leaked a tile to blue,
// audit #11) precisely because nothing enforced the mirror.
export const SOFT_EVIDENCE = new Set<string>([
  'pathway_declared',              // the student's own declared pathway (unverified)
  'utility_percapita_b40',         // soft income proxy from the utility bills
  'utility_percapita_high',
  'utility_hardship',
  'unemployment_epf_corroborated', // Phase 2B: EPF (all-zeros/lapsed) hinting unemployment — soft
  'household_size_confirm',        // Phase 2C: described people > stated household size — soft
])

/**
 * Map a verdict fact to a colour tone on a collapsed Kent confidence scale —
 * how sure the engine is that the fact is sound:
 *   verified  → green  (Certain  — checks passed)
 *   review    → blue   (Probable — ≥1 verified value backs it; confirm the rest)
 *             → amber  (Unsure   — review with NO verified value: declared-only /
 *                        soft-signal-only / incomplete. Blue requires a green.)
 *   recommend → amber  (Unsure   — even odds; the coordinator places the verdict)
 *   gap       → red    (Can't verify — missing/unreadable evidence)
 */
export function factTileTone(fact: AdminVerdictFact): FactTileTone {
  switch (fact.status) {
    case 'verified':
      return 'green'
    case 'recommend':
      return 'amber'
    case 'review': {
      // Probable needs a green: at least one genuinely-verified value, not just a
      // declaration or a soft signal. Otherwise it's Unsure.
      const hasVerified = fact.evidence.some((e) => !SOFT_EVIDENCE.has(e.code))
      return hasVerified ? 'blue' : 'amber'
    }
    case 'gap':
    default:
      return 'red'
  }
}

// The estimative-probability band each tone names (Kent scale, collapsed to four).
// Used for the tile labels + legend; the i18n key is admin.scholarship.verdict.band.<key>.
export const TONE_BAND_KEY: Record<FactTileTone, string> = {
  green: 'certain',
  blue: 'probable',
  amber: 'unsure',
  red: 'unverifiable',
}

// ── Document grouping ────────────────────────────────────────────────────────

export type DocFact = 'identity' | 'academic' | 'pathway' | 'income' | 'additional' | 'other'

/** Map a document's doc_type to the verification-fact section it belongs to. */
function docTypeToFact(docType: string): DocFact {
  switch (docType) {
    case 'ic':
      return 'identity'
    // Academic = the SPM slip AND the continuing-student current-CGPA slip.
    case 'results_slip':
    case 'semester_result':
      return 'academic'
    case 'offer_letter':
      return 'pathway'
    // The parent/guardian IC sits with INCOME: the income docs (STR / salary slip /
    // EPF) are issued in a parent's name, and the parent IC is what confirms that
    // earner's identity. The relationship docs (birth cert / guardianship letter) link
    // that earner to the student, so they belong to the income cluster too. Utility bills
    // lend credibility to the income claim (rendered in the UTILITY sub-section).
    case 'parent_ic':
    case 'str':
    case 'epf':
    case 'salary_slip':
    case 'birth_certificate':
    case 'guardianship_letter':
    case 'water_bill':
    case 'electricity_bill':
      return 'income'
    // Supporting context the student attaches to their case (not a verification fact).
    case 'statement_of_intent':
    case 'photo':
    case 'school_leaving_cert':
      return 'additional'
    // Everything else — reviewer-requested extras, income-support/bank/reference docs.
    case 'income_support_doc':
    case 'bank_statement':
    case 'reference_letter':
    case 'other':
    default:
      return 'other'
  }
}

export interface GroupedDocuments {
  identity: AdminApplicantDocument[]
  academic: AdminApplicantDocument[]
  pathway: AdminApplicantDocument[]
  income: AdminApplicantDocument[]
  additional: AdminApplicantDocument[]
  other: AdminApplicantDocument[]
  // Phase 2: replaced (superseded) documents — version history, kept out of every fact
  // group and shown under an "Old / Replaced" list so a superseded doc never reads as live.
  superseded: AdminApplicantDocument[]
}

/**
 * Group a flat list of documents under the verification-fact sections plus the
 * "additional" (supporting) and "other" (reviewer-requested extras) buckets. Any
 * superseded (replaced) document is diverted to the `superseded` bucket regardless of
 * its doc_type, so the fact sections only ever show the live copy.
 */
export function groupDocumentsByFact(
  documents: AdminApplicantDocument[],
): GroupedDocuments {
  const groups: GroupedDocuments = {
    identity: [],
    academic: [],
    pathway: [],
    income: [],
    additional: [],
    other: [],
    superseded: [],
  }
  for (const doc of documents) {
    if (doc.superseded_at) {
      groups.superseded.push(doc)
      continue
    }
    const fact = docTypeToFact(doc.doc_type)
    groups[fact].push(doc)
  }
  // Fixed within-section order. ACADEMIC: the SPM results slip first, the current-CGPA semester
  // slip below. ADDITIONAL: school-leaving cert → statement of intent → photo (anything else last;
  // "any other document/photo" lives in OTHER, not here).
  const orderBy = (list: AdminApplicantDocument[], order: string[]) => {
    const rank = (dt: string) => { const i = order.indexOf(dt); return i < 0 ? 99 : i }
    list.sort((a, b) => rank(a.doc_type) - rank(b.doc_type))
  }
  orderBy(groups.academic, ['results_slip', 'semester_result'])
  orderBy(groups.additional, ['school_leaving_cert', 'statement_of_intent', 'photo'])
  return groups
}

// ── AI suggestion summary ────────────────────────────────────────────────────

export type AiSuggest = 'yes' | 'no' | 'unsure'

export interface AiSuggestions {
  identity: AiSuggest
  academic: AiSuggest
  pathway: AiSuggest
  income: AiSuggest
}

/** Derive a plain yes / no / unsure suggestion from each fact's AI status. */
function statusToSuggest(status: AdminVerdictFact['status']): AiSuggest {
  if (status === 'verified') return 'yes'
  if (status === 'gap') return 'no'
  return 'unsure'
}

/**
 * Summarise the AI's verdict for each fact as a simple yes/no/unsure so the
 * record-verdict panel can render "AI suggested: Identity yes, Academic unsure…"
 * The coordinator then decides for themselves.
 */
export function aiSuggestionFor(verdictFacts: AdminVerdictFact[]): AiSuggestions {
  const defaults: AiSuggestions = {
    identity: 'unsure',
    academic: 'unsure',
    pathway: 'unsure',
    income: 'unsure',
  }
  for (const f of verdictFacts) {
    const key = f.fact as keyof AiSuggestions
    if (key in defaults) {
      defaults[key] = statusToSuggest(f.status)
    }
  }
  return defaults
}

// ── AI reliability (the scorekeeper — verification-assurance Sprint 3) ─────────

export const RELIABILITY_FACTS = ['identity', 'academic', 'pathway', 'income'] as const
export interface FactReliability { fact: string; decided: number; agree: number; pct: number }
export interface Reliability {
  applications: number
  perFact: FactReliability[]
  overall: { decided: number; agree: number; pct: number }
}

/** Turn the raw override metrics (how often the human DISAGREED with the AI) into the
 *  AGREEMENT view the card renders — per fact + overall. Agreement = 1 − override rate.
 *  Pure; `pct` is a 0–1 fraction (the component formats it). */
export function verdictReliability(m: VerdictMetrics): Reliability {
  const perFact = RELIABILITY_FACTS.map((fact) => {
    const f = m.per_fact?.[fact] || { decided: 0, overrides: 0 }
    const agree = Math.max(0, f.decided - f.overrides)
    return { fact, decided: f.decided, agree, pct: f.decided ? agree / f.decided : 0 }
  })
  const agree = Math.max(0, m.fact_decisions - m.overrides)
  return {
    applications: m.applications,
    perFact,
    overall: { decided: m.fact_decisions, agree, pct: m.fact_decisions ? agree / m.fact_decisions : 0 },
  }
}

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
    case 'partial': case 'uncertain': case 'pending': case 'stale': case 'unconfirmed': case 'check': case 'check_near':
      return 'partial'
    case 'mismatch': case 'unreadable': case 'not_found': case 'rejected':
      return 'not'
    default:                       // '', 'no_ref', 'unknown', undefined
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
    default: return 'unknown'   // unconfirmed / unreadable / rejected / wrong_type → date unknown or n/a
  }
}

/**
 * Tone for the STR APPROVAL status chip — the third required STR variable (after recipient
 * name + IC), distinct from the currency/date dimension above. Was it approved (Lulus)?
 *   current / stale / unconfirmed → all carry an approved status → green (Lulus).
 *   rejected (Ditolak) / wrong_type (not an STR at all) → red — no valid approval.
 *   unreadable (cropped page, status line not visible) → amber — couldn't read it, NOT a
 *     "not approved" (don't brand a cropped upload as rejected).
 */
function strStatusFactStatus(s: string | undefined | null): FactStatus {
  switch (s) {
    case 'current': case 'stale': case 'unconfirmed': return 'verified'
    case 'rejected': case 'wrong_type': return 'not'
    case 'unreadable': return 'partial'
    default: return 'unknown'
  }
}

/**
 * Tone for a utility-bill ADDRESS check. Mirrors the backend's weighted matcher + officer-flag
 * logic: only a genuine 'mismatch' (a different home) is red; 'unconfirmed'/'unreadable' (and the
 * legacy 'not_found') mean "couldn't confirm" — amber, eyeball at interview, never a hard miss.
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
// are meaningless. A `suspect` (looks like the right type but the fingerprints are thin — usually a
// cropped page) is AMBER 'genuine' — "we aren't sure it's genuine"; the read VALUES still stand on
// their own match/read status. null when there is no signal or the doc is genuine/likely_genuine.
function genuinenessFact(doc: AdminApplicantDocument): DocumentFactLabel | null {
  const s = doc.authenticity?.status
  if (!s || s === 'genuine' || s === 'likely_genuine') return null
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
    const facts: DocumentFactLabel[] = [
      { key: 'name', status: st(c.name) },
      { key: 'subjects', status: st(c.subjects) },
      { key: 'results', status: st(c.results) },
    ]
    if (gf) facts.push(gf)
    return facts
  }
  if (dt === 'offer_letter') {
    const c = doc.pathway_check
    if (!c) return []
    // Owner policy: an offer can settle identity + pathway ONLY if it is a genuine OFFICIAL
    // public offer. A non-genuine offer (conditional / private-IPTS / a non-official
    // pemakluman/semakan notification) can't confirm the pathway — so the Pathway VARIABLE goes
    // red (it establishes no pathway; the verdict counts this chip, `_pathway_red_chips`) and an
    // 'Official' fact surfaces the genuineness itself. Official is TWO-TONE (owner 2026-07-08):
    // RED for fake (`not_offer_letter` — not recognisably a proper offer), AMBER for suspect
    // (thin/cropped fingerprints — "we aren't sure"), matching the slip/IC chip semantics.
    const auth = doc.authenticity?.status
    const notOfficial = !!auth && auth !== 'genuine'
    const facts: DocumentFactLabel[] = [
      { key: 'name', status: factStatus(c.name) },
      { key: 'ic_no', status: factStatus(c.ic) },
    ]
    if (c.pathway) facts.push({ key: 'pathway', status: notOfficial ? 'not' : factStatus(c.pathway) })
    if (notOfficial) facts.push({ key: 'official', status: auth!.startsWith('not_') ? 'not' : 'partial' })
    return facts
  }
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
    // (hide it there when absent). Mirrors the STR chip — the number is the strong earner key.
    if ((c.nric || '').trim()) facts.push({ key: 'ic_no', status: cap ? 'not' : factStatus(c.nric_status) })
    if (dt === 'salary_slip') {
      // CONSISTENT chip set for every salary slip: Amount + Period always present, grey ('unknown')
      // when not read — never omitted, so two payslips don't show different numbers of chips.
      facts.push({ key: 'amount', status: (has('amount') || has('gross_income') || has('net_income')) ? 'verified' : 'unknown' })
      facts.push({ key: 'period', status: has('period') ? 'verified' : 'unknown' })
    } else {
      // EPF: surface what we already collect (the FE previously looked for a wrong key so NONE
      // showed). Contribution = the income figure; Balance = JUMLAH SIMPANAN; Date = statement
      // currency. Keys match income_engine.student_income_proof_check's EPF points.
      facts.push({ key: 'contribution', status: has('avgContribution') ? 'verified' : 'unknown' })
      facts.push({ key: 'balance', status: has('totalAccumulated') ? 'verified' : 'unknown' })
      facts.push({ key: 'current', status: has('statementDate') ? 'verified' : 'unknown' })
    }
    if (gf) facts.push(gf)
    return facts
  }
  if (dt === 'birth_certificate') {
    const c = doc.bc_check
    if (!c) return []
    return [
      { key: 'child', status: factStatus(c.child_status) },
      { key: 'mother', status: factStatus(c.mother_status) },
      { key: 'father', status: factStatus(c.father_status) },
    ]
  }
  if (dt === 'guardianship_letter') {
    const c = doc.guardianship_check
    if (!c) return []
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
    // Soft academic-completeness doc. The read is the officer signal (a blank is held on upload,
    // so a stored one that read is 'Evidence' verified); the officer opens it for the details.
    const vf = doc.vision_fields as { student_verdict?: string } | null | undefined
    if (!vf?.student_verdict) return []
    return [{ key: 'evidence', status: vf.student_verdict === 'ok' ? 'verified' : 'not' }]
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
    if (!c) return []
    // Address · Current · Reasonable always; Outstanding only when arrears > the charge
    // (a real hardship signal, shown green). 'current'/'stale'/'unknown' map through
    // factStatus directly (current→green, stale→amber, unknown→grey).
    const facts: DocumentFactLabel[] = [
      { key: 'address', status: addressFactStatus(c.address_status) },
      { key: 'current', status: factStatus(c.current_status) },
      { key: 'reasonable', status: reasonableStatus(c.reasonable_status) },
    ]
    if (c.outstanding_status === 'arrears') {
      facts.push({ key: 'outstanding', status: 'verified' })
    }
    return facts
  }
  return []
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

// ── Income section layout (route + selection aware) ──────────────────────────
// The income documents are shown COMPULSORY-on-top → OPTIONAL-at-the-bottom, and a
// compulsory doc that isn't uploaded shows as a "Missing" placeholder. The required
// slots are derived the same way the gate/wizard derive them (workingMembers +
// relationshipDocFor), so the cockpit can't disagree with what the student is asked for.

import { workingMembers, relationshipDocFor, MEMBER_ORDER, type WorkingMember } from '@/lib/incomeWizard'

export interface IncomeSlot {
  docType: string
  member: string                       // '' for STR / untagged household docs
  doc: AdminApplicantDocument | null   // the uploaded doc, or null = missing → placeholder
}

export interface IncomeLayout {
  required: IncomeSlot[]
  optional: AdminApplicantDocument[]
}

interface IncomeAnswerSource {
  income_route?: string | null
  income_earner?: string | null
  income_working_members?: string[] | null
}

/**
 * Order the income documents for the officer panel: the route's compulsory slots
 * first (STR: STR doc → earner IC → relationship doc; salary: per member IC → salary
 * slip → relationship doc), each carrying its uploaded doc or null (→ placeholder),
 * then any remaining uploaded income docs as OPTIONAL.
 */
export function incomeDocLayout(app: IncomeAnswerSource, incomeDocs: AdminApplicantDocument[]): IncomeLayout {
  const route = app.income_route || ''
  const find = (dt: string, member: string) =>
    incomeDocs.find((d) => d.doc_type === dt && (d.household_member || '') === member) || null
  const required: IncomeSlot[] = []
  if (route === 'str') {
    const earner = app.income_earner || ''
    // Slot model (TD-115): the STR earner's docs may be tagged with the earner OR carry the
    // legacy blank tag during the migration — match either so a backfilled IC/STR isn't read
    // as "missing". The relationship doc (applicant BC / guardian letter) is a single doc.
    const findE = (dt: string) =>
      incomeDocs.find((d) => d.doc_type === dt && [earner, ''].includes(d.household_member || '')) || null
    required.push({ docType: 'str', member: earner, doc: findE('str') })
    required.push({ docType: 'parent_ic', member: earner, doc: findE('parent_ic') })
    const rel = relationshipDocFor(earner)
    if (rel) required.push({ docType: rel, member: '', doc: findE(rel) })
  } else if (route === 'salary') {
    for (const m of workingMembers(app.income_working_members as WorkingMember[] | null)) {
      required.push({ docType: 'parent_ic', member: m, doc: find('parent_ic', m) })
      required.push({ docType: 'salary_slip', member: m, doc: find('salary_slip', m) })
      const rel = relationshipDocFor(m)
      if (rel && !required.some((s) => s.docType === rel)) {
        required.push({ docType: rel, member: '', doc: find(rel, '') })   // BC / letter — single, untagged
      }
    }
  }
  const usedIds = new Set(required.map((s) => s.doc?.id).filter((id): id is number => id != null))
  // Canonical optional order — income corroboration first (salary slip → EPF), then the
  // relationship proofs (BC / guardianship letter — e.g. a mononym student's father link),
  // then utility credibility bills. Mirrors the student wizard's order.
  const OPTIONAL_ORDER = ['salary_slip', 'epf', 'birth_certificate', 'guardianship_letter',
                          'water_bill', 'electricity_bill']
  const rank = (dt: string) => { const i = OPTIONAL_ORDER.indexOf(dt); return i < 0 ? 99 : i }
  const optional = incomeDocs.filter((d) => !usedIds.has(d.id))
    .sort((a, b) => rank(a.doc_type) - rank(b.doc_type))
  return { required, optional }
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
    if (!cs || cs === 'wrong_type' || cs === 'rejected') return false
    if (auth && auth !== 'genuine' && auth !== 'likely_genuine') return false
    return true
  })
  const salaryRequired = (app.income_route || '') !== 'str' && !strNotBreached
  const pushSlot = (docType: string, member: string, doc: AdminApplicantDocument | null) => {
    if (doc || salaryRequired) salary.push({ docType, member, doc })
  }
  for (const m of salaryMembers) {
    pushSlot('salary_slip', m, find('salary_slip', m))
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
    const epf = find('epf', m)
    if (epf) salary.push({ docType: 'epf', member: m, doc: epf })
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
// A per-doc-TYPE glyph so the icon space carries meaning (not just "is it an IC"); the row
// tints the badge by the doc's verdict. Emoji (the cockpit has no icon library).
const DOC_ICON: Record<string, string> = {
  ic: '🪪', parent_ic: '🪪', results_slip: '🎓', offer_letter: '🏫',
  str: '💵', salary_slip: '🧾', epf: '🏦', water_bill: '💧',
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

// ── Officer-decision gates ───────────────────────────────────────────────────
// Lifted verbatim out of the cockpit page (TD audit 2026-06-14) so the decision
// rules are pure + unit-testable, instead of inline IIFEs in 1,700 lines of JSX.

type OfficerVerdict = Record<string, string>

// Application states where a "save verdict = accept" can still apply (case still live).
export const LIVE_STATES = ['shortlisted', 'profile_complete', 'interviewing', 'interviewed']
// States (or a submitted interview) after which querying is closed and Outstanding is read-only.
export const QUERYING_LOCKED_STATES = ['interviewed', 'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected', 'withdrawn', 'expired']
// The four facts the officer rules on.
export const DECISION_FACTS = ['identity', 'academic', 'pathway', 'income'] as const

/** "Save verdict IS accept": identity passed, nothing failed, profile complete, case still live. */
export function isClearAccept(officerVerdict: OfficerVerdict, completenessComplete: boolean, status: string): boolean {
  return officerVerdict.identity === 'pass'
    && !(['academic', 'pathway', 'income'] as const).some((f) => officerVerdict[f] === 'fail')
    && !!completenessComplete && LIVE_STATES.includes(status)
}

/** Querying (raise / Resolve / Ask again / request doc) is closed once the interview is concluded. */
export function isQueryingLocked(status: string, interviewStatus?: string): boolean {
  return QUERYING_LOCKED_STATES.includes(status) || interviewStatus === 'submitted'
}

/** Approve/Decline activate only once the interview is submitted, all four facts are pass/fail, and a reason is written. */
export function isDecisionReady(interviewStatus: string | undefined, officerVerdict: OfficerVerdict, reason: string): boolean {
  return interviewStatus === 'submitted'
    && DECISION_FACTS.every((f) => officerVerdict[f] === 'pass' || officerVerdict[f] === 'fail')
    && (reason || '').trim().length > 0
}

/** Approve additionally requires a recommended assistance amount (the slider or an already-saved one). */
export function isApproveReady(decisionReady: boolean, hasAssistance: boolean): boolean {
  return decisionReady && hasAssistance
}

// ── Header lifecycle timeline ─────────────────────────────────────────────────

/** One chip in the cockpit header timeline. `labelKey` is the suffix under
 *  `admin.scholarship.*`; `at` is an ISO date (null → the step is pending, "—"). */
export interface HeaderTimelineStep { labelKey: string; at: string | null }

/** Minimal shape the timeline needs (a subset of AdminApplicationDetail). */
export interface TimelineSource {
  status: string
  submitted_at?: string | null
  recommended_at?: string | null
  awarded_at?: string | null
  active_at?: string | null
  maintenance_at?: string | null
}

// Once funded-and-executing, the header pivots to the post-award trio.
const TIMELINE_ACTIVE_PHASE = new Set(['active', 'maintenance', 'closed'])
// QC-cleared but not yet executing: the recommendation → award trio.
const TIMELINE_RECOMMENDED_PHASE = new Set(['recommended', 'awarded'])

/**
 * The three date chips for the header, chosen by lifecycle phase:
 *   • recommended / awarded            → Submitted · Recommended · Awarded
 *   • active / maintenance / closed    → Awarded · Active · Maintenance
 *   • anything earlier                 → null (the header keeps its default
 *                                        Submitted · Applied · Assigned line).
 * A step whose date is null renders as pending ("—").
 */
export function headerTimeline(app: TimelineSource): HeaderTimelineStep[] | null {
  if (TIMELINE_ACTIVE_PHASE.has(app.status)) {
    return [
      { labelKey: 'awarded', at: app.awarded_at ?? null },
      { labelKey: 'active', at: app.active_at ?? null },
      { labelKey: 'maintenance', at: app.maintenance_at ?? null },
    ]
  }
  if (TIMELINE_RECOMMENDED_PHASE.has(app.status)) {
    return [
      { labelKey: 'submitted', at: app.submitted_at ?? null },
      { labelKey: 'recommended', at: app.recommended_at ?? null },
      { labelKey: 'awarded', at: app.awarded_at ?? null },
    ]
  }
  return null
}
