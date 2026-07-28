/**
 * Sponsor comms — the pure decisions behind the Emails panel (S3, 2026-07-28).
 *
 * The twin of `partnerComms.ts`. The server is authoritative on every rule that matters (who may
 * edit, which tokens a kind supplies, what the voice guard refuses); this mirrors only what the
 * SCREEN has to decide — the order the nine kinds are listed in, and which copy key a refusal maps
 * to.
 */
import type { SponsorEmailTemplate } from './admin-api'

/**
 * Display order — lifecycle first, then the recurring sends.
 *
 * Deliberately NOT alphabetical and not the model's order: an admin reading this panel is
 * following a sponsor's journey (they register, they are vetted, they give, they hear about
 * students), and the list should read that way. The server returns its own order; the panel
 * re-sorts by this and drops anything it does not know, so a kind added server-side cannot appear
 * in a random position without someone deciding where it belongs.
 */
export const SPONSOR_EMAIL_KINDS = [
  'welcome',
  'approved',
  'rejected',
  'suspended',
  'reinstated',
  'credit_confirmed',
  'new_students',
  'weekly_digest',
  'referral_invite',
] as const

export type SponsorEmailKind = (typeof SPONSOR_EMAIL_KINDS)[number]

/** The nine, in journey order, ignoring anything the panel has no copy for. */
export function ordered(templates: SponsorEmailTemplate[]): SponsorEmailTemplate[] {
  return SPONSOR_EMAIL_KINDS
    .map((k) => templates.find((x) => x.kind === k))
    .filter((x): x is SponsorEmailTemplate => !!x)
}

/**
 * The three that reach sponsors TODAY through their pre-S3 hardcoded senders.
 *
 * They are seeded switched ON (owner, 2026-07-28), so normally their switch already tells the
 * truth. This list exists for the window before that seeding runs, and for the case where someone
 * switches one off while the platform gate is still shut — in both, the legacy sender is still
 * doing the work and an unqualified "off" would be a lie about an email that is going out.
 */
export const ALREADY_LIVE: readonly string[] = ['new_students', 'weekly_digest', 'referral_invite']

/**
 * Is this kind actually reaching sponsors right now?
 *
 * **Two different worlds, and the platform gate is the border.** While it is SHUT we are in the
 * pre-S3 world: templates are inert and only the three legacy senders run, whatever their
 * switches say. Once it is OPEN the templates govern completely — so `enabled` is the whole
 * answer, and switching an adopted email off genuinely stops it.
 */
export function sendsToday(kind: string, enabled: boolean, commsEnabled: boolean): boolean {
  return commsEnabled ? enabled : ALREADY_LIVE.includes(kind)
}

/** True when a row is sending DESPITE its own switch — the contradiction worth labelling. */
export function sendingDespiteSwitch(
  kind: string, enabled: boolean, commsEnabled: boolean,
): boolean {
  return !enabled && sendsToday(kind, enabled, commsEnabled)
}

/** How many templates are switched on — the panel's one-line summary. */
export function switchedOn(templates: SponsorEmailTemplate[]): number {
  return templates.filter((t) => t.enabled).length
}

/** Map a backend error code to its i18n key. Anything unmapped falls back to the generic. */
export function errorKey(code: string | undefined): string {
  if (code === 'unknown_placeholder') return 'admin.sponsors.emails.error.unknownPlaceholder'
  if (code === 'banned_phrasing') return 'admin.sponsors.emails.error.bannedPhrasing'
  if (code === 'subject_and_body_required') return 'admin.sponsors.emails.error.required'
  return 'admin.actionFailed'
}
