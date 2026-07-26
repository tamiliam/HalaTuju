/**
 * Partner emails — the pure decisions behind the Sources card (2026-07-26).
 *
 * The backend seam (`apps/scholarship/partner_comms.py`) is authoritative; this mirrors only what
 * the screen needs to RENDER, and deliberately mirrors no rule the server would refuse. In
 * particular the frontend never decides who qualifies — the server says so per organisation
 * (`qualifies`), because that decision reads `contact_email` and must never be re-derived from a
 * `PartnerAdmin` login (those belong to the HalaTuju course selector, not to this bursary).
 */
import type { PartnerEmailOrg, PartnerEmailTemplate } from './admin-api'

/** The five emails, in the order the card lists them. Mirrors `partner_comms.KINDS`. */
export const PARTNER_EMAIL_KINDS = [
  'weekly_summary',
  'shortlisted_followup',
  'awaiting_review',
  'awarded',
  'assigned',
] as const

export type PartnerEmailKind = (typeof PARTNER_EMAIL_KINDS)[number]

/** i18n key suffix per kind — one home, so a rename can't half-land. */
export function kindKey(kind: string): string {
  return `admin.sources.emails.kind.${kind}`
}

/**
 * Who an email would reach if it were switched on right now.
 *
 * `reachable` is what the card states out loud. On prod today it is 0 of 9 — nine referral
 * partners, none with a contact email — and saying so is the point: a switch that appears to work
 * while reaching nobody is worse than a switch that admits it.
 */
export function reach(orgs: PartnerEmailOrg[]): { reachable: number; partners: number } {
  const partners = orgs.filter((o) => !o.is_house_org)
  return { reachable: partners.filter((o) => o.qualifies).length, partners: partners.length }
}

/** The partners that cannot be reached — listed so the admin knows exactly what to fix. */
export function unreachable(orgs: PartnerEmailOrg[]): PartnerEmailOrg[] {
  return orgs.filter((o) => !o.is_house_org && !o.qualifies)
}

/** True when nobody at all can be reached — the card shows its amber banner. */
export function nobodyReachable(orgs: PartnerEmailOrg[]): boolean {
  return reach(orgs).reachable === 0
}

/**
 * Has this email ever actually gone out? Read from the send log, so a FAILED or skipped run never
 * reads as a success ("silence is not success", docs/lessons.md).
 */
export function everSent(tpl: PartnerEmailTemplate): boolean {
  return !!tpl.last_sent_at
}

/**
 * Insert a `{placeholder}` at the cursor of a textarea's value.
 * Returns the new value and where the caret should land, so the caller can restore it.
 */
export function insertPlaceholder(
  body: string, token: string, at: number,
): { value: string; caret: number } {
  const pos = Math.max(0, Math.min(at, body.length))
  return { value: body.slice(0, pos) + token + body.slice(pos), caret: pos + token.length }
}

/** Map a backend error code to its i18n key. Anything unmapped falls back to the generic. */
export function errorKey(code: string | undefined): string {
  if (code === 'unknown_placeholder') return 'admin.sources.emails.error.unknownPlaceholder'
  if (code === 'conduit_phrasing') return 'admin.sources.emails.error.conduitPhrasing'
  if (code === 'subject_and_body_required') return 'admin.sources.emails.error.required'
  return 'admin.actionFailed'
}
