/**
 * The shortlisted applicant's next-steps helpers — the Story label map, the tabbed shell, and what
 * a programme asks for (documents and questions).
 *
 * A LEAF, moved out of `scholarship.ts` VERBATIM (2026-10-05, the deploy gate's refusal of
 * `552cf494`: `/profile` read 310.007 kB against its 310 kB line). `scholarship.ts` rides whole on
 * `/profile`, `/scholarship/apply` and every admin route that imports it, and none of them uses
 * anything below; only `/scholarship/application`'s next-steps surface does. Nothing here was
 * reworded — only the imports are new.
 *
 * ⚠ The deeper-info form (`DetailsFormState` … `buildDetailsPayload`) was moved too and moved BACK
 * the same day: it is the one block importing `@/lib/familyRoster`, and taking that edge out of
 * `scholarship.ts` re-split the shared chunks so `/scholarship/application` grew 0.7 kB.
 */
import type { ApplicationCompleteness } from '@/lib/api'

// ── Save-error helpers (actionable validation messages) ──────────────────
// Maps a Story/Funding payload field key to the i18n key of the question label
// the student sees, so a "too long" save error can name the exact answer to fix.
export const STORY_FIELD_LABEL_KEYS: Record<string, string> = {
  // TD-259: this pointed at `…cardA.parentsOccupation`, a leaf the roster redesign removed, so
  // a "that answer is too long" error named a raw dotted path instead of a question. The field
  // is now DERIVED from the roster (`scholarship/family.parents_occupation_summary`), so the
  // question to send the student back to is the parents/guardians block itself.
  parents_occupation: 'scholarship.nextSteps.story.cardA.parentsHeading',
  family_context: 'scholarship.nextSteps.story.cardA.familyContext',
  aspirations: 'scholarship.nextSteps.story.cardB.aspirations',
  plans: 'scholarship.nextSteps.story.cardB.plans',
  daily_life: 'scholarship.nextSteps.story.cardB.dailyLife',
  fears: 'scholarship.nextSteps.story.cardB.fears',
  address: 'scholarship.nextSteps.story.cardAddress.street',
  city: 'scholarship.nextSteps.story.cardAddress.city',
  postal_code: 'scholarship.nextSteps.story.cardAddress.postal',
  funding_note: 'scholarship.nextSteps.funding.noteLabel',
}

// ── Next-steps tabbed shell (Sprint S1) ─────────────────────────────────

/**
 * The 5 tabs shown to a shortlisted applicant on /scholarship/application.
 * Referee has been moved to the admin verify-&-accept flow and is NOT in this list.
 */
// The wizard steps shown in the rail. 'review' is NOT a step here — it's a distinct
// page reached AFTER consent (via "Review & submit"), gated on completeness.
export const NEXT_STEP_ORDER = ['quiz', 'story', 'funding', 'documents', 'consent'] as const
export type NextStepKey = typeof NEXT_STEP_ORDER[number]

/**
 * Determine the initial tab: first incomplete step, falling back to 'quiz'.
 * Documents and Consent have no completeness signal yet (added in S4/S5),
 * so they are treated as always incomplete for the purpose of this default.
 */
export function defaultNextTab(
  completeness: { quiz_done: boolean; details_done: boolean; funding_done: boolean } | null | undefined,
): NextStepKey {
  if (!completeness) return 'quiz'
  if (!completeness.quiz_done) return 'quiz'
  if (!completeness.details_done) return 'story'
  if (!completeness.funding_done) return 'funding'
  return 'quiz'
}

/**
 * Whether a wizard step's required fields are all satisfied. Single source of
 * truth for both the step-rail's done-ticks and the "Save & continue" advance
 * gate (advance only when the step is complete). S14: the story tick needs the
 * narrative AND the address sub-section AND the family roster — all captured in
 * the one "Your story" tab, so the student sees a single consolidated done state.
 */
export function isStepComplete(k: NextStepKey, c: ApplicationCompleteness): boolean {
  switch (k) {
    case 'quiz': return c.quiz_done
    case 'story': return c.details_done && c.address_done && c.family_done
    case 'funding': return c.funding_done
    case 'documents': return c.documents_done
    case 'consent': return c.consent_done
    default: return false
  }
}

/** How a programme treats one document: shown with a marker, shown without, or not shown. */
export type DocRequirement = 'required' | 'optional' | 'off'

/**
 * What this programme asks for, for one document type.
 *
 * **An absent block means "we were not told", never "asks for nothing".** That distinction is the
 * whole lesson of Sprint 3a: resolving an unconfigured programme to the empty set made
 * `documents_done` vacuously true and would have let sixty students submit with no documents at
 * all. Here the failure would be quieter but the same shape — a Documents tab with no cards on it.
 * So a missing block degrades to `'optional'`: every card renders, nothing is asserted compulsory.
 * The front end displays; it has never been the gate, and `application_completeness` on the
 * server still decides whether a submission is allowed.
 *
 * `income_proof` is an aggregate — asking about it means "does this programme want the household
 * income section at all", not "is there a card called income proof".
 */
export function documentRequirement(
  requirements: { documents: { required: string[]; optional: string[] } } | null | undefined,
  docType: string,
): DocRequirement {
  const docs = requirements?.documents
  if (!docs) return 'optional'
  if (docs.required.includes(docType)) return 'required'
  if (docs.optional.includes(docType)) return 'optional'
  return 'off'
}

/** Is this document asked for at all (required OR optional)? */
export function asksForDocument(
  requirements: { documents: { required: string[]; optional: string[] } } | null | undefined,
  docType: string,
): boolean {
  return documentRequirement(requirements, docType) !== 'off'
}

// ── Questions (Layer 0 Sprint 4) ─────────────────────────────────────────

/**
 * The VOCABULARY of question codes, deliberately a static literal — the same rule as
 * `DOC_TYPES` above. What a programme ASKS is configuration and arrives on the payload
 * (`app.requirements.questions`); what a question IS stays a closed set an organisation
 * selects from and never authors. The four story codes are the backend field names.
 */
export const QUESTION_CODES = [
  'aspirations', 'plans', 'daily_life', 'fears',
  'family_roster', 'funding', 'address', 'consent',
  'justification', 'anything_else',
] as const
export type QuestionCode = typeof QUESTION_CODES[number]

type RequirementsShape = {
  documents: { required: string[]; optional: string[] }
  questions?: { required: string[]; optional: string[] }
} | null | undefined

/**
 * How this programme treats one question. Same contract as `documentRequirement`, and the
 * same absent-case rule (Sprint 3b's boundary): **a missing `questions` block means "we were
 * not told", never "asks nothing"** — degrade to `'optional'`, so every field renders and
 * nothing is asserted compulsory. The front end displays; `application_completeness` on the
 * server is the gate, exactly as for documents.
 */
export function questionRequirement(
  requirements: RequirementsShape,
  code: string,
): DocRequirement {
  const q = requirements?.questions
  if (!q) return 'optional'
  if (q.required.includes(code)) return 'required'
  if (q.optional.includes(code)) return 'optional'
  return 'off'
}

/** Is this question asked at all (required OR optional)? Off means: do not draw it. */
export function asksForQuestion(requirements: RequirementsShape, code: string): boolean {
  return questionRequirement(requirements, code) !== 'off'
}

// The four "About you" narrative questions — one Card B textarea each.
export const STORY_QUESTION_CODES = ['aspirations', 'plans', 'daily_life', 'fears'] as const

/**
 * The wizard steps THIS programme's configuration leaves visible — `NEXT_STEP_ORDER` (which
 * stays a static literal; a stored step list is Layer 2 in disguise) minus any step whose
 * questions are all switched off. COMPUTED at render, never stored, never re-orderable.
 *
 * Today only `funding` can collapse (its tab holds nothing but the funding questions). The
 * story step always survives: the family roster is a core catalogue item no organisation can
 * switch off, so Card A always has content even with all four narrative questions off.
 * Quiz, documents and consent are not question-governed here (documents has its own block;
 * consent is core).
 */
export function visibleNextSteps(requirements: RequirementsShape): NextStepKey[] {
  return NEXT_STEP_ORDER.filter((k) =>
    k !== 'funding' || asksForQuestion(requirements, 'funding'))
}
