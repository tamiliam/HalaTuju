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
