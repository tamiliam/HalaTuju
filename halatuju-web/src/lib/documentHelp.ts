// Pure logic for the "Cikgu Gopal" document-help coach. Kept framework-free so it
// is unit-testable in the project's node-env Jest (no DOM). The component
// (DocumentHelpCoach.tsx) is the only React part; all decisions live here.
import type { ApplicantDocument } from './api'

// Verdict codes the backend + these fallbacks share (same set as help_engine.VERDICT_GUIDANCE).
export const HELP_VERDICTS = [
  'name_mismatch',
  'nric_mismatch',
  'address_mismatch',
  'wrong_doc',
  'unreadable',
  'review_manually',
  // Results-slip specific (the three academic checks).
  'slip_name_mismatch',
  'slip_subjects_missing',
  'slip_grade_mismatch',
  // Results-slip — a grade read with low confidence (double-check), and a skewed photo
  // that left it unclear (retake straight). Pointed alternatives to a confident mismatch.
  'slip_grade_uncertain',
  'slip_skewed_unclear',
  // Offer-letter (pathway).
  'offer_name_mismatch',
  'offer_pathway_mismatch',
  // Income earner IC — the name doesn't link to the student's family (wrong IC uploaded).
  'income_relationship_mismatch',
  // Income proof (salary slip / EPF) — doesn't match the member's IC (different person).
  'income_proof_person_mismatch',
  // Income cluster — a proof was added for a member but their IC hasn't been uploaded yet.
  'income_ic_needed',
] as const

/**
 * Does this document have a soft problem worth a coach note? Mirrors the "non-good"
 * states of the existing chips (IC vision verdicts + supporting doc-assist / presence),
 * so the coach appears exactly where an amber/grey chip does — never under a green one.
 * Used to gate the network call so good/unchecked docs never hit the endpoint.
 */
export function shouldShowCoach(doc: ApplicantDocument): boolean {
  // IC / parent_ic — Vision OCR verdicts (only meaningful once Vision has run).
  if (doc.vision_run_at) {
    const nv = doc.vision_nric_verdict
    const mv = doc.vision_name_verdict
    if (nv === 'unreadable' || mv === 'unreadable') return true
    if (nv === 'mismatch' || mv === 'mismatch') return true
  }
  // Results slip — the academic 3-check fully decides (it's set only for results_slip).
  // Coach appears on any real problem, including a subjects/results mismatch the
  // generic "name found" chip would miss.
  if (doc.academic_check) {
    const ac = doc.academic_check
    return (
      ac.name === 'mismatch' ||
      ac.name === 'unreadable' ||
      ac.subjects === 'mismatch' ||
      ac.results === 'mismatch' ||
      ac.results === 'uncertain' ||   // a grade we couldn't be sure of → Gopal asks to double-check
      ac.subjects === 'unreadable' ||
      ac.results === 'unreadable'
    )
  }
  // Offer letter — the Name/IC identity checks, plus a soft offer-vs-declared
  // pathway mismatch (a gentle nudge, never a block). Set only for offer_letter.
  if (doc.pathway_check) {
    const pc = doc.pathway_check
    return pc.name === 'mismatch' || pc.ic === 'mismatch' || pc.pathway === 'mismatch'
  }
  // Income earner IC (parent_ic) — the single per-member CLUSTER coach is anchored here:
  // it speaks for the whole cluster (relationship + coherence across the member's IC +
  // income proofs). cluster_status (computed server-side) is non-empty iff there's advice.
  if (doc.income_ic_check) {
    return !!doc.income_ic_check.cluster_status
  }
  // Income proof (salary slip / EPF) — the cluster coach lives on the member's IC, so a
  // proof only coaches when there is NO IC yet (nudge to add it). When the IC is present
  // it anchors the coach and the proof stays quiet (no second Gopal for the same person).
  if (doc.income_proof_check) {
    return !doc.income_proof_check.ic_present
  }
  // Supporting docs — the Gemini doc-assist verdict takes precedence (matches the chip).
  const av = doc.vision_fields?.student_verdict
  if (av) return av !== 'ok'
  // Fallback: the older deterministic name/address presence checks.
  if (doc.vision_name_match && doc.vision_name_match !== 'found') return true
  if (doc.vision_address_match && doc.vision_address_match !== 'found') return true
  return false
}

/** i18n key for the pre-written fallback message, used when the AI is off/throttled.
 *  Unknown/absent verdict (e.g. a network error before the server replied) → a warm
 *  generic note rather than guessing the wrong specific reason. */
export function fallbackKeyFor(verdict: string | undefined): string {
  const v = (HELP_VERDICTS as readonly string[]).includes(verdict || '') ? verdict : 'generic'
  return `scholarship.docs.help.fallback.${v}`
}

// ── Coach advice cache ───────────────────────────────────────────────────────
// Cikgu Gopal must pop up only AFTER an upload, and his advice must STICK. We cache
// the fetched advice keyed by a "verdict signal" that changes only on a (re-)upload
// or re-run. So a plain page reload (same signal) re-renders the STORED advice with
// no network call and no re-pop; Gopal re-fires only when the signal changes.
// Storage-injectable so the node-env Jest can round-trip it with a Map-backed fake.

export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

function safeLocal(): StorageLike | null {
  try {
    return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null
  } catch {
    return null
  }
}

/** Changes whenever the document's verdict-relevant state changes (a re-upload /
 *  re-run). Compose with the language at the call site for a per-language key. */
export function helpSignal(doc: ApplicantDocument): string {
  const ac = doc.academic_check
  const pc = doc.pathway_check
  const ic = doc.income_ic_check
  const ip = doc.income_proof_check
  return [
    doc.vision_run_at || '',
    doc.vision_fields?.student_verdict || '',
    doc.vision_name_match || '',
    doc.vision_address_match || '',
    // Results slip / offer letter: the check can change when the student edits their
    // PROFILE (grades / name / NRIC) without re-uploading — fold it in to re-fire then.
    ac ? `${ac.name},${ac.subjects},${ac.results}` : '',
    pc ? `${pc.name},${pc.ic},${pc.pathway || ''}` : '',
    // Income earner IC: the cluster coach re-fires when the cluster verdict changes —
    // e.g. the student uploads a matching/ mismatching payslip, or the birth cert.
    ic ? `cluster:${ic.cluster_status || ''}` : '',
    // Income proof: re-fires when the member's IC appears (the add-IC nudge clears).
    ip ? `${ip.name_status},${ip.nric_status},${ip.ic_present ? 1 : 0}` : '',
  ].join('|')
}

export interface CachedHelp {
  source: 'ai' | 'fallback' | 'none'
  message: string
  verdict?: string
}

function helpCacheKey(docId: number, signal: string): string {
  return `halatuju_doc_help_${docId}_${signal}`
}

export function readHelpCache(
  docId: number, signal: string, storage: StorageLike | null = safeLocal(),
): CachedHelp | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(helpCacheKey(docId, signal))
    if (!raw) return null
    const v = JSON.parse(raw)
    if (v && (v.source === 'ai' || v.source === 'fallback' || v.source === 'none')) return v as CachedHelp
    return null
  } catch {
    return null
  }
}

export function writeHelpCache(
  docId: number, signal: string, value: CachedHelp, storage: StorageLike | null = safeLocal(),
): void {
  if (!storage) return
  try {
    storage.setItem(helpCacheKey(docId, signal), JSON.stringify(value))
  } catch {
    /* quota / disabled — non-fatal */
  }
}
