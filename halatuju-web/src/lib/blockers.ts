/**
 * Officer "Blockers" card — exactly what a student still owes, in the ADMIN's voice,
 * so the officer can advise them on the phone without asking for screenshots.
 *
 * The data is `application.consent_blockers` from the admin payload — the SAME list the
 * student's consent POST enforces (services.consent_blockers), so the officer and the
 * student can never be told different things. Nothing is recomputed here; this module
 * only maps codes → i18n keys and works out which wizard step to send them to.
 *
 * Pure functions only (no React), so they unit-test in a plain node env.
 */

// Statuses whose cockpit shows the Blockers card. `profile_complete` is included by owner
// decision (2026-07-22) and may be dropped later — delete the one entry, nothing else changes.
export const BLOCKER_BOX_STATUSES = ['shortlisted', 'profile_complete'] as const

export function showsBlockerBox(status: string | null | undefined): boolean {
  return (BLOCKER_BOX_STATUSES as readonly string[]).includes(status || '')
}

/**
 * Split a member-qualified code — the income gate emits `parent_ic_missing:mother` /
 * `salary_slip_missing:father` so the line can name the person. Everything else is bare.
 */
export function parseBlocker(raw: string): { code: string; member: string } {
  const [code = '', member = ''] = (raw || '').split(':')
  return { code, member }
}

/** The wizard step a blocker belongs to — drives the "currently stuck at" line. */
export type BlockerStep = 'quiz' | 'story' | 'funding' | 'documents'

// Only the section codes map to an earlier step. EVERYTHING else the consent gate can emit
// (missing / mismatched / unreadable documents, the household-income section, IC identity)
// is resolved in the Documents step — so `documents` is the default, and a code we don't
// know yet still lands somewhere sensible rather than breaking the line.
const STEP_OF: Record<string, BlockerStep> = {
  quiz_incomplete: 'quiz',
  story_incomplete: 'story',
  family_incomplete: 'story',
  address_incomplete: 'story',
  funding_incomplete: 'funding',
}

export function stepOf(code: string): BlockerStep {
  return STEP_OF[code] || 'documents'
}

const STEP_ORDER: BlockerStep[] = ['quiz', 'story', 'funding', 'documents']

/**
 * The EARLIEST step still holding the student up — where the officer should send them
 * first (they walk the wizard in order). Null when there are no blockers.
 */
export function stuckStep(codes: string[]): BlockerStep | null {
  const steps = new Set((codes || []).map((c) => stepOf(parseBlocker(c).code)))
  return STEP_ORDER.find((s) => steps.has(s)) || null
}

/**
 * i18n key for one blocker line. A member-qualified code uses the `_member` variant,
 * which interpolates the person's name (reusing the wizard's member labels).
 */
export function blockerLabelKey(raw: string): string {
  const { code, member } = parseBlocker(raw)
  return `admin.scholarship.blockers.item.${code}${member ? '_member' : ''}`
}

/** i18n key for a member's display name — the same labels the income wizard uses. */
export function memberLabelKey(member: string): string {
  return `scholarship.docs.income.wizard.member.${member}`
}
