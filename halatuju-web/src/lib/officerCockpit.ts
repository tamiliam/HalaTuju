/**
 * Pure logic for the Officer Review Cockpit (Sprint 5).
 *
 * All helpers are side-effect-free so they can be unit-tested in a plain
 * node env (no jsdom). The cockpit component consumes these; it never
 * re-implements them.
 */

import type { AdminVerdictFact, AdminApplicantDocument } from '@/lib/admin-api'

// ── Fact tile tone ───────────────────────────────────────────────────────────

export type FactTileTone = 'green' | 'amber' | 'blue' | 'red'

/**
 * Map a verdict fact status to a colour tone.
 *   verified  → green  (AI is confident, all checks passed)
 *   review    → amber  (AI flagged for coordinator to confirm)
 *   recommend → blue   (coordinator places the verdict, AI gives a steer)
 *   gap       → red    (action needed — something is missing or mismatched)
 */
export function factTileTone(status: AdminVerdictFact['status']): FactTileTone {
  switch (status) {
    case 'verified':
      return 'green'
    case 'review':
      return 'amber'
    case 'recommend':
      return 'blue'
    case 'gap':
    default:
      return 'red'
  }
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
    case 'partial': case 'uncertain': case 'pending': case 'stale':
      return 'partial'
    case 'mismatch': case 'unreadable': case 'not_found': case 'rejected':
      return 'not'
    default:                       // '', 'no_ref', 'unknown', undefined
      return 'unknown'
  }
}

const _PATRONYMIC_MEMBER = new Set(['father', 'brother', 'sister'])

/**
 * Tone for the combined-utility "Reasonable" fact. A soft B40 proxy, so it never shows
 * red: green when consumption is low, amber when borderline/high or only one bill was
 * given, grey when we can't judge at all.
 */
function reasonableStatus(s: string): FactStatus {
  if (s === 'reasonable') return 'verified'
  if (s === 'borderline' || s === 'high') return 'partial'
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
    const facts: DocumentFactLabel[] = [
      { key: 'name', status: factStatus(c.name) },
      { key: 'ic_no', status: factStatus(c.ic) },
    ]
    if (c.pathway) facts.push({ key: 'pathway', status: factStatus(c.pathway) })
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
      { key: 'address', status: factStatus(c.address_status) },
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
    required.push({ docType: 'str', member: '', doc: find('str', '') })
    required.push({ docType: 'parent_ic', member: '', doc: find('parent_ic', '') })
    const rel = relationshipDocFor(earner)
    if (rel) required.push({ docType: rel, member: '', doc: find(rel, '') })
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
  const optional = incomeDocs.filter((d) => !usedIds.has(d.id))
  return { required, optional }
}
