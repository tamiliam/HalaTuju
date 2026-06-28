/**
 * Pure logic for the Officer Review Cockpit (Sprint 5).
 *
 * All helpers are side-effect-free so they can be unit-tested in a plain
 * node env (no jsdom). The cockpit component consumes these; it never
 * re-implements them.
 */

import type { AdminVerdictFact, AdminApplicantDocument, VerdictMetrics } from '@/lib/admin-api'

// ── Fact tile tone ───────────────────────────────────────────────────────────

export type FactTileTone = 'green' | 'amber' | 'blue' | 'red'

// Evidence codes that are NOT a verified value — a self-declaration or a soft signal.
// "Probable" (blue) must rest on at least one real verified value, so a fact backed
// only by these (or by nothing) is "Unsure", not "Probable".
const SOFT_EVIDENCE = new Set<string>([
  'pathway_declared',        // the student's own declared pathway (unverified)
  'utility_percapita_b40',   // soft income proxy from the utility bills
  'utility_percapita_high',
  'utility_hardship',
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

export type DocFact = 'identity' | 'academic' | 'pathway' | 'income' | 'other'

/** Map a document's doc_type to the verification fact it belongs to. */
function docTypeToFact(docType: string): DocFact {
  switch (docType) {
    case 'ic':
      return 'identity'
    case 'results_slip':
      return 'academic'
    case 'offer_letter':
      return 'pathway'
    // The parent/guardian IC sits with INCOME: the income docs (STR / salary slip /
    // EPF) are issued in a parent's name, and the parent IC is what confirms that
    // earner's identity. The relationship docs (birth cert / guardianship letter) link
    // that earner to the student, so they belong to the income cluster too — without this
    // the BC fell to 'other' and the income panel showed it as a missing placeholder.
    // Utility bills lend credibility to the income claim.
    case 'parent_ic':
    case 'str':
    case 'epf':
    case 'salary_slip':
    case 'birth_certificate':
    case 'guardianship_letter':
    case 'water_bill':
    case 'electricity_bill':
      return 'income'
    default:
      return 'other'
  }
}

export interface GroupedDocuments {
  identity: AdminApplicantDocument[]
  academic: AdminApplicantDocument[]
  pathway: AdminApplicantDocument[]
  income: AdminApplicantDocument[]
  other: AdminApplicantDocument[]
}

/**
 * Group a flat list of documents under the four verification facts plus an
 * "other" bucket for anything we do not recognise.
 */
export function groupDocumentsByFact(
  documents: AdminApplicantDocument[],
): GroupedDocuments {
  const groups: GroupedDocuments = {
    identity: [],
    academic: [],
    pathway: [],
    income: [],
    other: [],
  }
  for (const doc of documents) {
    const fact = docTypeToFact(doc.doc_type)
    groups[fact].push(doc)
  }
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

/**
 * The coloured fact-labels for a document — only the facts that document provides.
 * Returns [] when the relevant check hasn't run (the row then renders as "unread").
 */
export function documentFacts(doc: AdminApplicantDocument): DocumentFactLabel[] {
  const dt = doc.doc_type
  if (dt === 'ic') {
    return [
      { key: 'name', status: factStatus(doc.vision_name_verdict) },
      { key: 'ic_no', status: factStatus(doc.vision_nric_verdict) },
    ]
  }
  if (dt === 'parent_ic') {
    const c = doc.income_ic_check
    if (!c) return []
    // The earner IC PROVIDES Name + IC No (legible = verified). It provides the
    // RELATIONSHIP only for a father/elder-sibling (patronymic); mother/guardian prove
    // it via the BC / guardianship letter, so no relationship label here.
    const read: FactStatus = c.readable ? 'verified' : 'not'
    const facts: DocumentFactLabel[] = [
      { key: 'name', status: read },
      { key: 'ic_no', status: read },
    ]
    if (_PATRONYMIC_MEMBER.has(c.member)) {
      facts.push({ key: 'relationship', status: factStatus(c.name_status) })
    }
    return facts
  }
  if (dt === 'results_slip') {
    const c = doc.academic_check
    if (!c) return []
    return [
      { key: 'name', status: factStatus(c.name) },
      { key: 'subjects', status: factStatus(c.subjects) },
      { key: 'results', status: factStatus(c.results) },
    ]
  }
  if (dt === 'offer_letter') {
    const c = doc.pathway_check
    if (!c) return []
    // Owner policy: an offer can settle identity + pathway ONLY if it is a genuine OFFICIAL
    // public offer. A non-genuine offer (conditional / private-IPTS / a non-official
    // pemakluman/semakan notification) can't confirm the pathway — so an 'Official' fact goes
    // red and Pathway can never show green off a letter we don't accept. This keeps the chip in
    // step with the verdict tile (which gates on the same signal).
    const auth = doc.authenticity?.status
    const notOfficial = !!auth && auth !== 'genuine'
    const facts: DocumentFactLabel[] = [
      { key: 'name', status: factStatus(c.name) },
      { key: 'ic_no', status: factStatus(c.ic) },
    ]
    if (c.pathway) facts.push({ key: 'pathway', status: notOfficial ? 'not' : factStatus(c.pathway) })
    if (notOfficial) facts.push({ key: 'official', status: 'not' })
    return facts
  }
  if (dt === 'str') {
    const c = doc.str_check
    if (!c) return []
    return [
      { key: 'recipient', status: factStatus(c.name_status) },
      { key: 'ic_no', status: factStatus(c.nric_status) },
      { key: 'current', status: factStatus(c.current_status) },
    ]
  }
  if (dt === 'salary_slip' || dt === 'epf') {
    const c = doc.income_proof_check
    if (!c) return []
    const has = (k: string) => (c.points || []).some((p) => p.key === k && (p.value || '').trim())
    const facts: DocumentFactLabel[] = [{ key: 'name', status: factStatus(c.name_status) }]
    if (dt === 'salary_slip') {
      if (has('amount') || has('gross_income') || has('net_income')) facts.push({ key: 'amount', status: 'verified' })
      if (has('period')) facts.push({ key: 'period', status: 'verified' })
    } else if (has('monthlyContribution') || has('monthly_contribution')) {
      facts.push({ key: 'contribution', status: 'verified' })
    }
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

import { workingMembers, relationshipDocFor, type WorkingMember } from '@/lib/incomeWizard'

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
