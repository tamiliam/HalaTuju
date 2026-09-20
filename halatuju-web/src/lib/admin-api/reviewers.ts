/**
 * The reviewer roster (request #10): the workload maths, the detail, their gift, and the
 * pause switch.
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (1426-1436, 3570-3671, 3841-3852) — `listReviewers`
 * and `getReviewerDetail` sat 170 lines below their own types, behind the org-config calls.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

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
 * ⚠ The gift field is ONE gift (`programme_id`), never a list. It was absent by decision until
 * 2026-09-04 — *"with one programme the column could only say one thing; it comes back when a
 * second programme exists"* — and a second gift now exists, so the ruling's own clause fired.
 */
export interface AdminReviewer {
  id: number
  name: string
  email: string
  role: string
  /** Fluency codes the reviewer can actually interview in — 'conversational' or better. */
  languages: string[]
  open_now: number
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
  /** The gift they cover. **NULL = every gift**, the permissive default with no backfill —
   *  render it as "every gift", never as a blank cell that reads as missing data. */
  programme_id: number | null
  programme_name: string
}

/** A gift the caller may scope a reviewer to. Includes gifts that are not switched on yet:
 *  a gift is staffed BEFORE it opens. */
export interface AdminReviewerGift {
  id: number
  code: string
  name: string
  is_active: boolean
}

/**
 * Which gift a reviewer covers. Passing `null` clears it, and clearing means EVERY gift —
 * there is no state in which somebody is offered nothing.
 *
 * ⚠ A NARROWING, NEVER A FENCE. It decides who is OFFERED a case; the org boundary is
 * server-side and untouched, and a reviewer already holding another gift's case keeps it.
 */
export async function setReviewerProgramme(
  reviewerId: number, programmeId: number | null, options?: ApiOptions,
): Promise<{ id: number; programme_id: number | null; programme_name: string }> {
  return adminMutate(`/api/v1/admin/reviewers/${reviewerId}/programme/`, 'POST',
    { programme_id: programmeId }, options)
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

