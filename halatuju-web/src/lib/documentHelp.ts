// Pure logic for the "Cikgu Gopal" document-help coach. Kept framework-free so it
// is unit-testable in the project's node-env Jest (no DOM). The component
// (DocumentHelpCoach.tsx) is the only React part; all decisions live here.
import type { ApplicantDocument } from './api'
import { relationshipDocFor, type WorkingMember } from './incomeWizard'

// Verdict codes the backend + these fallbacks share (same set as help_engine.VERDICT_GUIDANCE).
export const HELP_VERDICTS = [
  'name_mismatch',
  'nric_mismatch',
  // Student's own IC: name matched but only the IC number didn't — likely an OCR misread.
  'ic_nric_misread',
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
  // Income cluster — IC is in + matches the proof; the relationship doc (birth cert /
  // guardianship letter) is the last required step to link the earner to the student.
  'income_rel_doc_needed',
  // STR document is out of date (older year / not approved) — STR is awarded annually.
  'str_not_current',
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
  // STR — currency (stale/rejected) is intrinsic to the STR so it coaches HERE; recipient
  // coherence is voiced by the earner-IC cluster coach. Also nudge if no earner IC yet.
  if (doc.str_check) {
    const s = doc.str_check
    return s.current_status === 'stale' || s.current_status === 'rejected' || !s.ic_present
  }
  // Utility bill — the meaningful check is the HOME ADDRESS, never the (parent's) name. So
  // coach ONLY on an address mismatch (the old "name doesn't match you" nudge is wrong here).
  if (doc.utility_check) {
    return doc.utility_check.address_status === 'not_found'
  }
  // Relationship-proof docs (birth cert / guardianship letter) — the per-row checklist shows
  // the detail and any relationship problem is voiced by the earner-IC cluster coach, so the
  // doc itself stays quiet (no wrong generic name/address nudge).
  if (doc.bc_check || doc.guardianship_check) {
    return false
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

// ── Income cluster grouping (the single per-earner coach) ────────────────────
// Income is a cluster per earner; the coach is anchored at the foot of the cluster (not on
// one file). These helpers pick the documents that belong to a member's cluster so the
// cluster coach can gate its fetch + build a cache signal that re-fires on any cluster change.

const INCOME_EVIDENCE = new Set(['parent_ic', 'salary_slip', 'epf'])

/**
 * The documents in one earner's income cluster.
 *  - STR route: a single earner; income docs are stored UNTAGGED — the STR + evidence
 *    (IC / payslip / EPF) + the relationship doc (birth cert / guardianship letter).
 *  - salary route: this member's TAGGED evidence + the (untagged) relationship doc.
 */
export function clusterDocsFor(
  docs: ApplicantDocument[], member: string, route: string,
): ApplicantDocument[] {
  const rel = relationshipDocFor(member as WorkingMember)   // '' | 'birth_certificate' | 'guardianship_letter'
  if (route === 'str') {
    return docs.filter((d) => {
      const untagged = (d.household_member || '') === ''
      return untagged && (d.doc_type === 'str' || INCOME_EVIDENCE.has(d.doc_type) || (!!rel && d.doc_type === rel))
    })
  }
  return docs.filter((d) => {
    const m = d.household_member || ''
    return (INCOME_EVIDENCE.has(d.doc_type) && m === member) || (!!rel && d.doc_type === rel && m === '')
  })
}

/** A signal that changes whenever any document in the cluster changes (upload / re-run /
 *  verdict). Compose with the language at the call site. */
export function clusterHelpSignal(clusterDocs: ApplicantDocument[]): string {
  return clusterDocs
    .map((d) => `${d.id}:${helpSignal(d)}`)
    .sort()
    .join('||')
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
    // STR: re-fires when currency / recipient match / earner-IC presence changes.
    doc.str_check ? `str:${doc.str_check.current_status},${doc.str_check.name_status},${doc.str_check.ic_present ? 1 : 0}` : '',
    // Utility: re-fires when the address match changes.
    doc.utility_check ? `util:${doc.utility_check.address_status}` : '',
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

/** Read/write a cached coach result by a fully-formed key — shared by the per-document
 *  cache (keyed by docId) and the income-cluster cache (keyed by member). */
export function readHelpCacheRaw(
  key: string, storage: StorageLike | null = safeLocal(),
): CachedHelp | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(key)
    if (!raw) return null
    const v = JSON.parse(raw)
    if (v && (v.source === 'ai' || v.source === 'fallback' || v.source === 'none')) return v as CachedHelp
    return null
  } catch {
    return null
  }
}

export function writeHelpCacheRaw(
  key: string, value: CachedHelp, storage: StorageLike | null = safeLocal(),
): void {
  if (!storage) return
  try {
    storage.setItem(key, JSON.stringify(value))
  } catch {
    /* quota / disabled — non-fatal */
  }
}

export function readHelpCache(
  docId: number, signal: string, storage: StorageLike | null = safeLocal(),
): CachedHelp | null {
  return readHelpCacheRaw(helpCacheKey(docId, signal), storage)
}

export function writeHelpCache(
  docId: number, signal: string, value: CachedHelp, storage: StorageLike | null = safeLocal(),
): void {
  writeHelpCacheRaw(helpCacheKey(docId, signal), value, storage)
}

/** Cache key for the income-cluster coach (per earner, per signal). */
export function clusterCacheKey(member: string, signal: string): string {
  return `halatuju_income_help_${member}_${signal}`
}
