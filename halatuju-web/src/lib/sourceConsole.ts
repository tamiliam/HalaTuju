/**
 * The source console's vocabulary (source sign-in S3 + S4, 2026-10-30) — pure, node-testable.
 *
 * ⚠ THE STAGES ARE THE SERVER'S. `SOURCE_STAGES` is `source_console.STAGES`, which is the partner
 * emails' own `partner_comms.STAGE_LINES` in email order; a drift test reads that table. What is
 * the web's own is only the WORDS, chosen for what each line actually holds:
 *
 *   not_shortlisted  status `submitted` — sent, the shortlist has not looked at it yet  → "Sent"
 *   shortlisted      shortlisted, the application is not complete yet ("Shortlisted —
 *                    application incomplete" in the partner email)                    → "Missing items"
 *   awaiting_review  `profile_complete` — complete, waiting for the panel             → "Waiting for review"
 *   under_review     interviewing / interviewed / recommended — `recommended` is folded
 *                    in ON PURPOSE (C12): it must not reach a source as a near-certainty → "Under review"
 *   awarded          awarded / active / maintenance — the student has been told        → "Awarded"
 *   rejected         a decline the student has been told of                           → "Not selected"
 *   closed           withdrawn / expired / closed                                     → "Closed"
 *
 * An embargoed decline is NOT `rejected` here: the server folds the student's own masked status,
 * so it reads as the stage it was declined from until the student is told.
 * drift-test: halatuju-web/src/lib/__tests__/sourceConsoleDrift.test.ts
 */
import type { SourceContract, SourceStage } from '@/lib/admin-api'

export const SOURCE_STAGES: readonly SourceStage[] = [
  'not_shortlisted', 'shortlisted', 'awaiting_review', 'under_review', 'awarded', 'rejected', 'closed',
]

const K = 'admin.sourceConsole'

export const stageLabelKey = (stage: string) => `${K}.stage.${stage}`

/** Tone per stage — the console's own semantic colours: blue in progress, amber where the source
 *  can help (items missing), green awarded, red not selected, grey ended. Literal class names, so
 *  Tailwind's scanner sees them. */
const STAGE_TONE: Record<SourceStage, string> = {
  not_shortlisted: 'bg-info-50 text-info-700',
  shortlisted: 'bg-caution-100 text-caution-700',
  awaiting_review: 'bg-info-100 text-info-700',
  under_review: 'bg-info-100 text-info-800',
  awarded: 'bg-positive-100 text-positive-800',
  rejected: 'bg-critical-100 text-critical-700',
  closed: 'bg-ground-100 text-ground-600',
}

export const stageTone = (stage: string) =>
  STAGE_TONE[stage as SourceStage] ?? 'bg-ground-100 text-ground-600'

/** The qualification the student holds results for (`results_held`): spm / stpm / matric /
 *  asasi / diploma, or '' — shown as a dash. */
const LEVELS = ['spm', 'stpm', 'matric', 'asasi', 'diploma']
export const levelLabelKey = (level: string) => `${K}.level.${LEVELS.includes(level) ? level : 'none'}`

/** The checklist parts a source may see by NAME on one shortlisted application
 *  (`source_console.PARTS`) — never a document type or an income route. */
const PARTS = ['quiz', 'story', 'funding', 'documents', 'consent', 'address', 'guardian_documents', 'family']
export const partLabel = (t: (k: string) => string, part: string) =>
  (PARTS.includes(part) ? t(`${K}.part.${part}`) : part)

/** A scholar's status as the STUDENT has it (review L8): awarded, then "Active" while the bursary
 *  runs — `maintenance` is a staff word (the student's own pages never print it) — then closed. */
export const scholarStatusKey = (status: string) =>
  `${K}.scholarStatus.${status === 'maintenance' ? 'active'
    : ['awarded', 'active', 'closed'].includes(status) ? status : 'active'}`

/** The contract's stage, in the words the Scholars file already uses (`admin.scholars.contract`). */
export const contractStageKey = (stage: SourceContract['status'] | null | undefined) =>
  `admin.scholars.contract.${stage ?? 'none'}`

/** A refusal code from a source-console write → its message key, or the generic one. */
export function refusalKey(group: 'witness' | 'profile', code: string | undefined): string {
  const known: Record<typeof group, string[]> = {
    witness: ['not_ready', 'already_witnessed', 'contract_not_live', 'confirm_required',
      'name_required', 'name_too_long', 'not_found', 'source_unavailable'],
    profile: ['name_required', 'source_name_required', 'bad_email', 'not_editable', 'source_unavailable'],
  }
  return `${K}.${group}.error.${code && known[group].includes(code) ? code : 'generic'}`
}
