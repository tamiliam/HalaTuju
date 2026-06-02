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

export type DocFact = 'identity' | 'academic' | 'income' | 'pathway' | 'other'

/** Map a document's doc_type to the verification fact it belongs to. */
function docTypeToFact(docType: string): DocFact {
  switch (docType) {
    case 'ic':
    case 'parent_ic':
      return 'identity'
    case 'results_slip':
      return 'academic'
    case 'str':
    case 'epf':
    case 'salary_slip':
    case 'water_bill':
    case 'electricity_bill':
      return 'income'
    case 'offer_letter':
      return 'pathway'
    default:
      return 'other'
  }
}

export interface GroupedDocuments {
  identity: AdminApplicantDocument[]
  academic: AdminApplicantDocument[]
  income: AdminApplicantDocument[]
  pathway: AdminApplicantDocument[]
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
    income: [],
    pathway: [],
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
  income: AiSuggest
  pathway: AiSuggest
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
    income: 'unsure',
    pathway: 'unsure',
  }
  for (const f of verdictFacts) {
    const key = f.fact as keyof AiSuggestions
    if (key in defaults) {
      defaults[key] = statusToSuggest(f.status)
    }
  }
  return defaults
}

// ── Document pill ────────────────────────────────────────────────────────────

export type DocumentPill = 'verified' | 'check' | 'unread'

/**
 * Derive a display pill for a document from its Vision OCR signal fields.
 *
 * The pill is a coarse summary the coordinator sees at a glance:
 *   verified — both NRIC and name matched (where applicable), or name/address
 *              found on supporting docs.
 *   check    — there is a mismatch or partial match that needs attention.
 *   unread   — Vision has not run, or the document has not been processed yet.
 */
export function documentPill(doc: AdminApplicantDocument): DocumentPill {
  // IC: use the harder verdict fields (nric_verdict / name_verdict)
  if (doc.doc_type === 'ic' || doc.doc_type === 'parent_ic') {
    const nric = doc.vision_nric_verdict
    const name = doc.vision_name_verdict
    if (!nric && !name) return 'unread'
    if (
      (nric === 'match' || nric === '') &&
      (name === 'match' || name === '')
    ) {
      // At least one must be a positive match to call it verified.
      if (nric === 'match' || name === 'match') return 'verified'
    }
    if (
      nric === 'mismatch' ||
      name === 'mismatch' ||
      name === 'partial' ||
      nric === 'unreadable' ||
      name === 'unreadable'
    ) {
      return 'check'
    }
    return 'unread'
  }

  // Supporting documents: use the softer name/address presence signals.
  const nameMatch = doc.vision_name_match
  const addrMatch = doc.vision_address_match
  if (!nameMatch && !addrMatch) return 'unread'
  if (nameMatch === 'found' || addrMatch === 'found') return 'verified'
  if (nameMatch === 'not_found' || nameMatch === 'unreadable') return 'check'
  if (addrMatch === 'not_found' || addrMatch === 'unreadable') return 'check'
  return 'unread'
}
