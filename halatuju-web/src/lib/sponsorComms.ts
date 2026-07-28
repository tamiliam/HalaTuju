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
 * Which kinds are LIVE today via their pre-S3 hardcoded sender, and so are already reaching
 * sponsors while their template is switched off.
 *
 * The panel says so on those rows. Without it the screen would read "off" against an email that
 * is demonstrably going out, which is the kind of quiet contradiction this module exists to stop.
 */
export const ALREADY_LIVE: readonly string[] = ['new_students', 'weekly_digest', 'referral_invite']

export function sendsToday(kind: string, enabled: boolean, commsEnabled: boolean): boolean {
  return (commsEnabled && enabled) || ALREADY_LIVE.includes(kind)
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
