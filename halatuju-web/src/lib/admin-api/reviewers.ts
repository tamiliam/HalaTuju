/**
 * The reviewer roster (request #10): the workload maths, the detail, their gifts, and the
 * pause switch.
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (1426-1436, 3570-3671, 3841-3852) — `listReviewers`
 * and `getReviewerDetail` sat 170 lines below their own types, behind the org-config calls.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { TeamRemove } from './admins'

/**
 * Step a reviewer back from NEW work, or bring them back — the admin's route (super/org_admin).
 *
 * The reviewer's own route is a `paused` field on their profile PATCH. Both go through one service,
 * so "paused" cannot mean two things depending on who pressed it.
 */
export async function setReviewerPaused(id: number, paused: boolean, options?: ApiOptions) {
  return adminMutate<{ id: number; paused: boolean; paused_at: string | null }>(
    `/api/v1/admin/reviewers/${id}/pause/`, 'POST', { paused }, options)
}

// ── Reviewers (Organisation → Reviewers, request #10, 2026-08-02) ─────────────

/**
 * One row of the reviewers table.
 *
 * Every figure is org-fenced and computed server-side; nothing here is re-derived on the client.
 * There is deliberately **no corrections count** — reopens live on the detail page, with their
 * reasons, because a bare number beside a volunteer's name reads as a competence score.
 *
 * ⚠ The gifts are a LIST (`gifts`) since multi-gift tagging (owner design, 2026-11-06): a reviewer
 * may cover two of three gifts. `[]` means EVERY gift — the default.
 */
export interface AdminReviewer {
  id: number
  name: string
  email: string
  role: string
  /** Fluency codes the reviewer can actually interview in — 'conversational' or better. */
  languages: string[]
  /** Common profile S2: the optional fourth language by NAME, '' when none (beside the codes). */
  other_language?: string
  /** Both kinds together. Kept for the revoke warning, which counts interviews too. */
  open_now: number
  /** Request #51: open now's two halves — they always sum to `open_now`. */
  awaiting_review: number
  interviewing: number
  completed: number
  /** MEDIAN days from assignment to verdict. `null` = no completed review, NOT zero. */
  turnaround_days: number | null
  /** Stepped back from NEW work. Never a revoke — see `PartnerAdmin.paused_at`. */
  paused: boolean
  paused_at: string | null
  /** ⚠ REVOKED IS NOT PAUSED. False = the account is closed; they keep their row (so Restore is
   *  reachable) and can never be assigned a case. 2026-09-09. */
  is_active: boolean
  /** NULL is "not recorded", NEVER "never signed in" — the backfill is best-effort. */
  last_seen_at: string | null
  /** The gifts they cover, by code. **`[]` = every gift**, the default — render it as "Every
   *  gift", never as a blank cell that reads as missing data. */
  gifts: ReviewerGiftTag[]
  /** Their organisation — the pop-over offers only its gifts (a super is served every org's). */
  organisation_id?: number | null
  /** Common profile S2: a ~1-hour signed URL of their photo, or null. Staff screens only. */
  photo_url?: string | null
  /** Their phone ONLY when they show it to the team ("Show my phone to my team"), else null. */
  phone?: string | null
  /** Request #39 Sprint 4 — the permission chips, the same three fields as `AdminItem`. */
  custom?: boolean
  permissions_added?: string[]
  permissions_removed?: string[]
  /** Team tables T2: the same seat fields as `AdminItem` (`staff_tables_admin.row_fields`). */
  tables?: string[]
  lead?: boolean
  admin_keys?: string[]
  reviewer_keys?: string[]
  remove?: TeamRemove
  /** Sprint T2 (D6): may this viewer DELETE them outright (no work on record), and the work that
   *  stops it, `{what: count}` — the Admins table's two fields, by the same server rule. */
  deletable?: boolean
  /** T2 review N2: nobody may ever delete this row here — draw no Delete. */
  delete_never?: boolean
  /** T2 review N3: Revoke / Restore may be offered (false: a super, yourself, the sole org admin). */
  revocable?: boolean
  work?: Record<string, number>
}

/** One gift a reviewer covers, as served (`staff_gift.gifts_payload`). */
export interface ReviewerGiftTag {
  id: number
  code: string
  name: string
}

/** A gift the caller may scope a reviewer to. Includes gifts that are not switched on yet:
 *  a gift is staffed BEFORE it opens. */
export interface AdminReviewerGift extends ReviewerGiftTag {
  is_active: boolean
  /** Multi-gift: a super is offered every organisation's gifts, but a reviewer may be tagged only
   *  with their OWN organisation's (the server refuses any other with a 404). */
  organisation_id?: number
}

/**
 * Which gifts a reviewer covers — the whole list. `[]` means EVERY gift: there is no state in
 * which somebody is offered nothing.
 *
 * ⚠ IT BLOCKS ASSIGNMENT, NOT READING (owner, 2026-11-06): the server refuses `gift_mismatch` for a
 * new case outside these gifts. A case the person already holds is not taken away.
 */
export async function setReviewerGifts(
  reviewerId: number, programmeIds: number[], options?: ApiOptions,
): Promise<{ id: number; gifts: ReviewerGiftTag[] }> {
  return adminMutate(`/api/v1/admin/reviewers/${reviewerId}/programme/`, 'POST',
    { programme_ids: programmeIds }, options)
}

/** One reopened decision, with the reason recorded at the time it was reopened. */
export interface AdminReviewerReopen {
  id: number
  application_id: number
  reason: string
  reopened_by: string
  at: string
}

/**
 * One reviewer, whole.
 *
 * The contact block is a deliberate, PARTIAL widening of a self-scoped profile: phone yes, **home
 * address never** — it is not serialised at all, and a backend test asserts it cannot appear.
 * See `docs/scholarship/role-matrix.md`.
 */
export interface AdminReviewerDetail extends AdminReviewer {
  /** The gift choices behind the picker on this page — the caller's own organisation's. */
  programmes: AdminReviewerGift[]
  /**
   * The four outcome bands. They PARTITION the decided cases, so they always sum to `completed`
   * and the bar can never disagree with the figure above it.
   *
   * ⚠ `declined` is a rejection THEY recorded; `rejected_after_review` is one somebody else
   * recorded on a case they reviewed. Colouring the two alike accuses a reviewer of a decision
   * they did not make.
   */
  recommended: number
  declined: number
  rejected_after_review: number
  awaiting_qc: number
  created_at: string
  qualification: string
  university: string
  graduation_year: number | null
  field_of_study: string
  phone: string
  share_phone_with_students: boolean
  reopens: AdminReviewerReopen[]
  /** #39 S4: would the pause endpoint ACCEPT this person (`set_paused`'s own target rule)? Absent
   *  on an older payload, which is read as "yes" — what the page assumed before it existed. */
  pausable?: boolean
}

export async function listReviewers(
  options?: ApiOptions,
): Promise<{ reviewers: AdminReviewer[]; programmes: AdminReviewerGift[] }> {
  return adminFetch('/api/v1/admin/reviewers/', options)
}

export async function getReviewerDetail(
  id: number, options?: ApiOptions,
): Promise<AdminReviewerDetail> {
  return adminFetch(`/api/v1/admin/reviewers/${id}/`, options)
}

