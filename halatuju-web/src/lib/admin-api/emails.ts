/**
 * Every e-mail template an officer authors: the partner set, the reviewer set, the
 * invitation set, the sponsor set, and the read-only reviewer system e-mails.
 *
 * ⚠ TWO SPANS of the old `admin-api.ts` (514-595 and 748-811) — the sponsor-terms authoring
 * module was written between the template TYPES and the calls that read them.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Partner emails (2026-07-26) ───────────────────────────────────────────
// Five programme-wide emails to the referral organisations that run this bursary alongside us.
// One switch per email — on means every QUALIFYING partner receives it; there is no
// per-organisation choice (owner ruling).

export interface PartnerEmailTemplate {
  kind: string
  enabled: boolean
  /** True for the one email on this screen the STUDENT receives, not the partner organisation. */
  to_student: boolean
  /** True for the five our own REVIEWERS receive. Server-computed, so the label cannot drift. */
  to_reviewer: boolean
  subject: string
  body: string
  placeholders: string[]
  updated_by_email: string
  updated_at: string | null
  last_sent_at: string | null
  last_sent_orgs: number
}

export interface PartnerEmailOrg {
  id: number
  code: string
  name: string
  students: number
  has_email: boolean
  is_house_org: boolean
  qualifies: boolean
}

export interface PartnerEmailsPayload {
  templates: PartnerEmailTemplate[]
  organisations: PartnerEmailOrg[]
  /** How many organisations an email would actually reach today. */
  qualifying_count: number
  /** Referral partners in total — the house organisation is not one of them. */
  partner_count: number
  /** The platform flag. Settings still save while it is off; nothing sends. */
  comms_enabled: boolean
}

// ---- Sponsor comms (S3, 2026-07-28) ----
// The twin of the partner-email pair. One switch per EMAIL, not per sponsor: a sponsor is not a
// tenant, and "which donors hear about a new student" is not a per-donor decision.

export interface SponsorEmailTemplate {
  kind: string
  /** The model's own human label for the kind — the panel prefers its i18n copy. */
  label: string
  enabled: boolean
  subject: string
  body: string
  placeholders: string[]
  updated_by_email: string
  updated_at: string | null
  last_sent_at: string | null
  last_sent_count: number
}

export interface SponsorEmailsPayload {
  templates: SponsorEmailTemplate[]
  /** The PLATFORM gate. Switches still save while it is off; nothing sends. */
  comms_enabled: boolean
  /** Seeded vs expected — a mismatch means the seed command has not been run. */
  seeded: number
  expected: number
  sponsor_count: number
}

export async function getSponsorEmails(options?: ApiOptions): Promise<SponsorEmailsPayload> {
  return adminFetch('/api/v1/admin/scholarship/sponsor-emails/', options)
}

export async function updateSponsorEmail(
  kind: string,
  patch: { enabled?: boolean; subject?: string; body?: string },
  options?: ApiOptions,
): Promise<SponsorEmailTemplate> {
  return adminMutate(`/api/v1/admin/scholarship/sponsor-emails/${kind}/`, 'PATCH', patch, options)
}

export async function getPartnerEmails(options?: ApiOptions) {
  return adminFetch<PartnerEmailsPayload>('/api/v1/admin/scholarship/partner-emails/', options)
}

/**
 * The five emails OUR REVIEWERS receive — the same endpoint, asked for by family.
 *
 * They are edited on Organisation -> Reviewers, not Sources: a reviewer is not a referral partner,
 * and a template about our own volunteers filed under "Partner emails" would be shelved where
 * nobody looking for it would look. The default (unfiltered) call deliberately excludes them.
 */
export async function getReviewerEmails(options?: ApiOptions) {
  return adminFetch<PartnerEmailsPayload>(
    '/api/v1/admin/scholarship/partner-emails/?family=reviewer', options)
}

/**
 * The TWO invitation emails, edited on Organisation -> Invitations.
 *
 * A third family alongside partner and reviewer. They are deliberately off the Sources screen for
 * the same reason the reviewer ones are: an email about joining this organisation is not a partner
 * email, and filing it there shelves it where nobody looking for it would look.
 */
export async function getInvitationEmails(options?: ApiOptions) {
  return adminFetch<PartnerEmailsPayload>(
    '/api/v1/admin/scholarship/partner-emails/?family=invite', options)
}

/** One of the reviewer emails nobody can edit, rendered by the code that sends it. */
export type ReviewerSystemEmail = {
  key: string
  /** The SHAPE — the letter with `{ref}`, `{interview_time}` and friends left as names. */
  subject: string
  body: string
  /** The same letter with real particulars filled in. Both come from one builder server-side. */
  sample_subject: string
  sample_body: string
  sensitive: boolean
  wider_audience: boolean
}

/**
 * The SEVEN reviewer emails that are ours to maintain — shown so that at least they are known.
 *
 * Owner ruling, 2026-08-02: left off the screen they "exist in the background without anyone
 * paying attention to them until something breaks". Deliberately NOT a `PartnerEmailTemplate`:
 * there is no row, no switch and no editor behind any of it, and being code-owned prose is the
 * fact the section exists to state. The subject and body come from the senders' own builders, so
 * this cannot show wording we do not actually send.
 */
export async function getReviewerSystemEmails(options?: ApiOptions) {
  return adminFetch<{ emails: ReviewerSystemEmail[] }>(
    '/api/v1/admin/reviewers/system-emails/', options)
}

export async function updatePartnerEmail(
  kind: string,
  data: Partial<{ enabled: boolean; subject: string; body: string }>,
  options?: ApiOptions,
) {
  return adminMutate<PartnerEmailTemplate>(
    `/api/v1/admin/scholarship/partner-emails/${kind}/`, 'PATCH', data, options)
}

