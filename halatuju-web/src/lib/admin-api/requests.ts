/**
 * The Requests space (Sprint 15): a request, its conversation, its AI analysis, its quote and
 * schedule, and its screenshot attachments.
 *
 * ⚠ TWO SPANS of the old `admin-api.ts` (2140-2275 and 2698-2865). The whole billing and
 * invoicing module was written between the request TYPES and the calls that act on them; the
 * split puts the domain back together, which is one of the two the roadmap promised for free.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ---- Requests space (Sprint 15) ----
// Bug/feature requests → AI reviewer → owner-gated hours quotes. Dark behind REQUESTS_ENABLED:
// every route 404s while off, which is how the Administration hub card ships dark (the count
// probe 404s → the card is hidden; no client flag).

/**
 * One entry in a request's DISCUSSION (TD-201) — the replacement for the `clarifications`
 * question/answer pairs, which are no longer on either payload.
 *
 * A QUESTION IS A COMMENT AWAITING A REPLY (`awaiting_reply`), which is what makes this one
 * stream rather than a thread of questions with a separate comment log beside it.
 *
 * ⚠ `visibility: 'internal'` NEVER reaches an org_admin — the server filters the ROWS out of the
 * org payload (`org_requests.comments_for`). It appears in this type because the SUPER payload
 * carries both, and the detail page badges an internal comment so the owner can see at a glance
 * what the requester cannot. Do not treat its absence client-side as the protection; the
 * protection is server-side and tested there.
 */
export interface OrgRequestComment {
  id: number
  // WHO spoke. 'ai' is the reviewer and 'engineer' is the approved analysis (TD-204) — neither has
  // a PartnerAdmin row, so `author_name` is '' for both.
  // ⚠ Every value here needs `admin.requests.detail.author.<kind>` in en/ms/ta: the thread renders
  // that key from the value, so a missing one prints a raw dotted path to the requester.
  author_kind: 'ai' | 'owner' | 'org' | 'engineer'
  author_name: string
  body: string
  visibility: 'shared' | 'internal'
  awaiting_reply: boolean
  created_at: string
}

/** A screenshot attached to a request (Sprint 15.1). download_url is a signed Supabase URL or
 *  null (denied when the blob's key-org disagrees with the request's org). */
export interface OrgRequestAttachment {
  id: number
  original_filename: string
  content_type: string
  size: number
  created_at: string
  download_url: string | null
}

/**
 * The engineer's working paper behind one comment (TD-204) — **OWNER-ONLY**.
 *
 * ⚠ This never appears on an org_admin's payload. The analysis reaches the requesting organisation
 * as PROSE, through `comments`, authored `engineer`; the CITED FILES and the ENGINEER'S HOURS stay
 * owner-side. Neither is secrecy: a citation the requester cannot open buys them nothing while the
 * paths disclose the internal shape of a multi-tenant platform, and a second hours figure in front
 * of them recreates what removing the AI's estimate fixed. The field is optional on
 * `OrgRequestDetail` for exactly that reason — an org payload does not carry it at all.
 */
export interface OrgRequestAnalysis {
  id: number
  body: string
  estimated_hours: string | null
  cited_files: string[]
  authored_by: string
  repo_sha: string
  /** The engineer's PROPOSED triage. It prefills the owner's form and applies nothing — the
   *  request's own kind/lane change only when the owner presses Run. '' means "no opinion",
   *  which is not the same as agreeing with the AI draft. */
  proposed_kind: string
  proposed_lane: string
  created_at: string
  approved_at: string | null
  approved_by_name: string
  superseded_at: string | null
  /** The one the quote gate reads — server-computed, so the screen and the gate cannot disagree. */
  is_current: boolean
}

/** The ORG-facing payload (what a submitting org_admin sees) — the allowlist. NEVER carries the
 *  AI draft (ai_*) or the owner's triage. The owner (super) additionally receives the owner
 *  fields below (all optional here). */
export interface OrgRequestDetail {
  id: number
  kind: string
  title: string
  description: string
  // Optional Bugzilla-style scoping (owner-approved Sprint 15 increment); '' when unset.
  component: string
  urgency: string
  steps_to_reproduce: string
  status: string
  // The discussion, oldest first. Filtered to `shared` for an org_admin, server-side.
  comments: OrgRequestComment[]
  attachments: OrgRequestAttachment[]
  quote_hours: string | null
  quote_note: string
  quoted_at: string | null
  approved_at: string | null
  scheduled_for: string | null
  decline_reason: string
  created_at: string
  updated_at: string
  submitted_by_name: string
  // Owner-only (super payload) — undefined in the org payload by construction.
  organisation_id?: number
  organisation_name?: string
  // The margin is owner-only (owner, 2026-07-30: "do not mention the margin"). It is off the ORG
  // serializer entirely, not merely hidden in the UI, so an org payload cannot carry it.
  quote_margin_pct?: number | null
  // The engineer's analyses, newest first (TD-204). Owner-only — see OrgRequestAnalysis.
  analyses?: OrgRequestAnalysis[]
  ai_run_count?: number
  ai_draft_kind?: string
  ai_draft_lane?: string
  ai_draft_hours?: string | null
  ai_draft_note?: string
  ai_draft_model?: string
  ai_draft_at?: string | null
  triaged_kind?: string
  lane?: string
  triage_note?: string
  triaged_at?: string | null
  declined_by_role?: string
}

export async function getOrgRequests(
  filters?: { status?: string }, options?: ApiOptions
): Promise<{ requests: OrgRequestDetail[] }> {
  const qs = filters?.status ? `?status=${encodeURIComponent(filters.status)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/requests/${qs}`, options)
}

export async function getOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminFetch(`/api/v1/admin/scholarship/requests/${id}/`, options)
}

/** The lean badge probe. 404s while REQUESTS_ENABLED is off → callers hide the hub card. */
export async function getOrgRequestCount(options?: ApiOptions): Promise<{ count: number }> {
  return adminFetch('/api/v1/admin/scholarship/requests/count/', options)
}

export async function createOrgRequest(
  data: {
    kind: string; title: string; description: string; organisation_id?: number
    component?: string; urgency?: string; steps_to_reproduce?: string
  },
  options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate('/api/v1/admin/scholarship/requests/', 'POST', data, options)
}

// Requestee (org_admin) actions
/**
 * Reply to an open question. `comment_id` names WHICH question the answer is against; omitted —
 * which is what the single reply box sends — it is the oldest open one.
 *
 * ⚠ It does NOT ration what closes. The requester speaking settles every question standing before
 * their reply, by design, so naming one never leaves the others hanging. Do not build a per-question
 * chooser on the promise that it would; it would offer a distinction the server does not make.
 *
 * ⚠ The dead `index` parameter lived here until 2026-08-18. The server renamed it `comment_id` on
 * 2026-07-31 and nothing on either side was updated, so every answer 500-ed for eighteen days.
 */
export async function answerOrgRequest(
  id: number, data: { answer: string; comment_id?: number }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/answer/`, 'POST', data, options)
}
/**
 * The OWNER asks the requester a question — the other half of the clarification thread, which
 * until 2026-07-30 only the AI could write to. Super-only server-side.
 */
export async function askOrgRequest(
  id: number, data: { question: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/ask/`, 'POST', data, options)
}
/**
 * Post to the DISCUSSION (TD-201) — a STATEMENT, not a question, so it awaits no reply and does
 * not spend the reviewer's question budget.
 *
 * Open to the super AND to any org_admin of the owning organisation: they can already read the
 * request, so this lets the people already in the room speak rather than only watch.
 *
 * `visibility: 'internal'` is SUPER-ONLY — the server answers 403 for anyone else, and an org
 * author can never be internal at all. Omit it for the ordinary shared case.
 */
export async function commentOrgRequest(
  id: number, data: { body: string; visibility?: 'shared' | 'internal' }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/comments/`, 'POST', data, options)
}
/**
 * Stage the engineer's analysis as a DRAFT (TD-204). Super-only; posts nothing.
 *
 * Normally written by the `record_request_analysis` management command, which additionally checks
 * that every cited path exists in the repo. This client exists so the same thing can be done from
 * the cockpit — but a citation typed here is NOT existence-checked, which is the command's whole
 * advantage.
 */
export async function recordOrgRequestAnalysis(
  id: number,
  data: { body: string; estimated_hours?: string; cited_files: string[]; authored_by?: string },
  options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/analysis/`, 'POST', data, options)
}
/** The owner approves an analysis and it enters the thread as an `engineer` comment. Super-only. */
export async function approveOrgRequestAnalysis(
  id: number, analysisId: number, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/analysis/${analysisId}/approve/`,
                     'POST', {}, options)
}
/** Retire a DRAFT analysis the engineer got wrong, so it cannot be approved by mistake. */
export async function withdrawOrgRequestAnalysis(
  id: number, analysisId: number, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/analysis/${analysisId}/withdraw/`,
                     'POST', {}, options)
}
export async function approveOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/approve/`, 'POST', {}, options)
}
export async function deferOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/defer/`, 'POST', {}, options)
}
export async function modifyOrgRequest(
  id: number, data: { description: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/modify/`, 'POST', data, options)
}
export async function declineOrgRequest(
  id: number, data: { reason?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/decline/`, 'POST', data, options)
}

// Owner (super) actions
export async function triageOrgRequest(
  id: number, data: { triaged_kind: string; lane: string; note?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/triage/`, 'POST', data, options)
}
export async function quoteOrgRequest(
  id: number, data: { hours: number; margin_pct?: number; note?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/quote/`, 'POST', data, options)
}
export async function requoteOrgRequest(
  id: number, data: { hours: number; margin_pct?: number; note?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/requote/`, 'POST', data, options)
}
export async function scheduleOrgRequest(
  id: number, data: { scheduled_for?: string }, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/schedule/`, 'POST', data, options)
}
export async function doneOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/done/`, 'POST', {}, options)
}
export async function aiRerunOrgRequest(id: number, options?: ApiOptions): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/ai-rerun/`, 'POST', {}, options)
}

// ---- Screenshot attachments (Sprint 15.1) ----
// The upload is the sign -> PUT bytes to Supabase -> record chain (ActionCentre.tsx:187 pattern);
// see uploadOrgRequestAttachment for the whole flow.
async function signOrgRequestAttachment(
  id: number, options?: ApiOptions
): Promise<{ upload_url: string; storage_path: string }> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/attachments/sign-upload/`, 'POST', {}, options)
}

async function recordOrgRequestAttachment(
  id: number,
  payload: { storage_path: string; original_filename: string; content_type: string; size: number },
  options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/attachments/`, 'POST', payload, options)
}

export async function deleteOrgRequestAttachment(
  id: number, attId: number, options?: ApiOptions
): Promise<OrgRequestDetail> {
  return adminMutate(`/api/v1/admin/scholarship/requests/${id}/attachments/${attId}/`, 'DELETE', null, options)
}

/** The whole upload chain: sign → PUT the bytes straight to Supabase → record the row. Returns the
 *  refreshed request (with the new attachment). Throws on any step (caller shows a warning). */
export async function uploadOrgRequestAttachment(
  id: number, file: File, options?: ApiOptions
): Promise<OrgRequestDetail> {
  const { upload_url, storage_path } = await signOrgRequestAttachment(id, options)
  const resp = await fetch(upload_url, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': file.type || 'application/octet-stream', 'x-upsert': 'true' },
  })
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`)
  return recordOrgRequestAttachment(id, {
    storage_path,
    original_filename: file.name,
    content_type: file.type || 'application/octet-stream',
    size: file.size,
  }, options)
}

