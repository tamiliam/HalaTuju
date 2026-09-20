/**
 * Sponsor account vetting (Phase E): the queue, the review decision, the detail payload,
 * memberships, and the wallet credits recorded against them.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Phase E: sponsor account vetting ──
export interface AdminSponsor {
  id: number
  name: string
  email: string
  phone: string
  source: string
  organisation: string
  note: string
  status: 'pending' | 'approved' | 'rejected' | 'suspended'
  reviewed_at: string | null
  reviewed_by: string
  created_at: string
  /** Confirmed money, ORG-FENCED (a tenant sees its own share). Always a 2dp string. */
  given: string
  /** Students this sponsor is currently holding money for. Fenced the same way `given` is. */
  students: number
  /** Null until this sponsor next opens their portal — nothing recorded it before 2026-07-27. */
  last_seen_at: string | null
}

/** One wallet. The sponsor's money is per (sponsor, programme) — never a single pooled figure. */
export interface AdminSponsorWallet {
  programme_id: number | null
  programme_name: string
  given: string
  committed: string
  available: string
  credits: number
  students: number
}

export interface AdminSponsorCredit {
  id: number
  programme_id: number | null
  programme_name: string
  amount: string
  source: string
  external_reference: string
  status: 'draft' | 'admin_signed' | 'finance_checked' | 'confirmed' | 'cancelled'
  is_spendable: boolean
  recorded_by: string
  recorded_at: string | null
  finance_checked_by: string
  finance_checked_at: string | null
  confirmed_by: string
  confirmed_at: string | null
  created_at: string
}

export interface AdminSponsorStudent {
  id: number
  application_id: number
  /** The ANONYMOUS code the sponsor sees — the vocabulary both sides share. */
  ref: string
  programme_name: string
  amount: string
  status: string
  offered_at: string | null
  decided_at: string | null
}

/**
 * One sponsor, whole. The ACCOUNT is platform-level and shown in full; the money and the
 * students are fenced to the caller's organisation — `fenced` says which you are looking at.
 */
export interface AdminSponsorDetail {
  id: number
  name: string
  email: string
  phone: string
  organisation: string
  source: string
  note: string
  status: 'pending' | 'approved' | 'rejected' | 'suspended'
  is_trusted: boolean
  created_at: string
  reviewed_at: string | null
  reviewed_by: string
  last_seen_at: string | null
  consent_at: string | null
  consent_version: string
  notify_frequency: 'realtime' | 'weekly' | 'off'
  last_digest_sent_at: string | null
  programmes: AdminSponsorWallet[]
  credits: AdminSponsorCredit[]
  sponsorships: AdminSponsorStudent[]
  referrals: Array<{
    id: number
    invitee_name: string
    invitee_email: string
    status: string
    created_at: string
    joined_at: string | null
  }>
  memberships: Array<{
    /** Null only on a legacy row with no programme; the credit form skips those. */
    programme_id: number | null
    programme_name: string
    status: string
    vetted_by: string
    vetted_at: string | null
  }>
  /**
   * Every gift this admin may accept the benefactor into — the choices behind the accept /
   * move panel. INCLUDES inactive gifts (`is_active: false`): a second gift is created
   * switched off and staffed before it opens, so the panel must offer it.
   */
  assignable_programmes: Array<{
    id: number
    code: string
    name: string
    is_active: boolean
  }>
  /** Live, never stored — appointing a finance admin arms the credit chain's middle step. */
  finance_check_required: boolean
  /** True when this caller sees only their own organisation's share of the account. */
  fenced: boolean
}

export async function getSponsorDetail(id: number, options?: ApiOptions): Promise<AdminSponsorDetail> {
  return adminFetch(`/api/v1/admin/sponsors/${id}/`, options)
}

/**
 * Accept a benefactor into one of THIS organisation's gifts, or take it back.
 *
 * ⚠ THIS IS THE CALL THAT UNBLOCKS THE MONEY. `record_admin_credit` refuses
 * `sponsor_not_in_programme` without an approved membership, and until S-ASSIGN the only
 * writer hard-coded the flagship — so a second gift's first credit needed an engineer.
 *
 * The server refuses `programme_required`, `bad_status` and `account_not_approved`; a gift
 * outside the caller's organisation is 404, never 403.
 */
export async function setSponsorMembership(
  id: number,
  body: { programme_id: number; status: 'pending' | 'approved' | 'rejected' | 'suspended' },
  options?: ApiOptions
): Promise<{ programme_id: number; programme: string; status: string }> {
  return adminMutate(`/api/v1/admin/sponsors/${id}/membership/`, 'POST', body, options)
}

export async function listSponsors(status?: string, options?: ApiOptions): Promise<{ sponsors: AdminSponsor[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return adminFetch(`/api/v1/admin/sponsors/${q}`, options)
}

/** Lean count of sponsor accounts awaiting vetting — drives the nav + Administration-hub badge. */
export async function getPendingSponsorCount(options?: ApiOptions): Promise<{ count: number }> {
  return adminFetch('/api/v1/admin/sponsors/pending-count/', options)
}

export async function reviewSponsor(
  id: number, action: 'approve' | 'reject' | 'suspend', options?: ApiOptions
): Promise<AdminSponsor> {
  return adminMutate(`/api/v1/admin/sponsors/${id}/review/`, 'POST', { action }, options)
}

// ---- Wallet credits (P4b endpoints, live since 2026-07-27; UI added in sponsor S2) ----
// These three have existed and been org-fenced on the server since P4b; until now nothing
// called them, so every credit was keyed in by a developer. The chain is
// draft → admin_signed → [finance_checked] → confirmed, and `sign` posts to ONE endpoint
// whichever step is next — the service decides which, so the client never names a step.

/** Record an off-platform gift as a `draft`. `external_reference` is the bank ref, mandatory. */
export async function recordSponsorCredit(
  body: { sponsor_id: number; programme_id: number; amount: string; external_reference: string },
  options?: ApiOptions,
): Promise<AdminSponsorCredit> {
  return adminMutate('/api/v1/admin/scholarship/credits/', 'POST', body, options)
}

/** Sign whichever step is next. The typed name must match the caller's own admin record. */
export async function signSponsorCredit(
  id: number, typedName: string, options?: ApiOptions,
): Promise<AdminSponsorCredit> {
  return adminMutate(`/api/v1/admin/scholarship/credits/${id}/sign/`, 'POST',
    { typed_name: typedName }, options)
}

/** Void an UNCONFIRMED credit. The row is kept — a confirmed credit is never cancelled. */
export async function voidSponsorCredit(
  id: number, options?: ApiOptions,
): Promise<AdminSponsorCredit> {
  return adminMutate(`/api/v1/admin/scholarship/credits/${id}/cancel/`, 'POST', null, options)
}

