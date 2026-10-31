/**
 * The staff of an organisation: who they are, inviting one, revoking one, resending an
 * invitation, and setting a password.
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (168-218, 284-352, 821-862). The invitation READER
 * (`./invitations`) was written in the middle of them, and `inviteAdmin` 500 lines later.
 */
import { API_BASE, adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Admin management ────────────────────────────────────────────────

export interface AdminItem {
  id: number
  name: string
  email: string
  is_super_admin: boolean
  role: 'super' | 'admin' | 'org_admin' | 'partner' | 'reviewer' | 'qc' | 'finance'
  is_active: boolean
  org_name: string | null
  owning_org_id?: number | null
  owning_org_name?: string | null
  created_at: string
  /** A reviewer who has stepped back. Serialised here as well as on the Reviewers table, so the
   *  two screens showing the same people can no longer disagree about it. */
  paused?: boolean
  paused_at?: string | null
  /** NULL means NOT RECORDED, never "never signed in" — everyone predating 2026-08-03 is empty. */
  first_seen_at?: string | null
  last_seen_at?: string | null
  /** ⚠ MAY THIS VIEWER ACT ON THIS ROW? Everybody in the tenant is LISTED; only some may be
   *  revoked — an org_admin sees their fellow organisation admins and may not touch them. Served
   *  by the same check the write endpoints enforce, so the screen cannot draw a refused button. */
  manageable?: boolean
  /** Common profile S2: a ~1-hour signed URL of their photo, or null. Staff screens only. */
  photo_url?: string | null
  /** Their phone ONLY when they show it to the team ("Show my phone to my team"), else null. */
  phone?: string | null
  /** Whether this account may be DELETED outright rather than only revoked: an admin-shaped role
   *  with NO recorded work. Reviewers are never deletable (owner, 2026-09-09). */
  deletable?: boolean
  /** What this person has DONE, `{what: count}`, empty when nothing. The reason a delete is
   *  refused, so the screen can name it instead of greying a button for no visible cause. */
  work?: Record<string, number>
  /** Request #39 Sprint 4 — People's permission chips. `custom` = a set saved on the editor; the two
   *  lists are what differs from the preset (both empty on it), decided by the server. */
  custom?: boolean
  permissions_added?: string[]
  permissions_removed?: string[]
  /** THIS row's dormancy threshold, resolved for the person's own organisation on the server
   *  (Org Config Sprint C). `standingOf` reads it; the old constant is only its fallback. */
  dormant_days?: number
  /** The invitation behind this person. Null when they predate the record. */
  invitation?: {
    /** Decided by the server (`invitations.status_of`); never re-derived on this side. */
    status: 'invited' | 'expired' | 'no_reply' | 'accepted' | 'revoked'
    sent_at: string | null
    send_count: number
    /** Tri-state: true sent, false a real failure, **null not recorded** (every backfilled row). */
    last_send_ok: boolean | null
    last_send_error: string
    expires_at: string | null
    credential_issued: boolean
  } | null
}

export async function getAdmins(options?: ApiOptions) {
  return adminFetch<{ admins: AdminItem[] }>('/api/v1/admin/admins/', options)
}

/** Delete a staff account outright. ⚠ Only ever offered for an admin-shaped role with NO recorded
 *  work; the server refuses everything else — 409 `has_work` carries the counts that stopped it,
 *  400 `not_deletable` means the role can never be deleted (every reviewer). */
export async function deleteAdmin(adminId: number, options?: ApiOptions) {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(body.error || `Delete failed: ${res.status}`) as Error & { code?: string }
    err.code = body.code || body.error || ''
    throw err
  }
  // `login: 'failed'` = the row is gone but their sign-in could not be removed; the message says so.
  return res.json() as Promise<{ message: string; login?: string }>
}

/** Switch a person within their pair (Admin ↔ Finance, Reviewer ↔ QC — `lib/staffRole`).
 *  `dryRun` asks what the switch WOULD do without writing: `consequence` says whether the
 *  payment finance check switches on or off, so the confirmation can say so before the click.
 *  A refusal throws with the server's sentence as the message and its `code`. */
export async function changeAdminRole(adminId: number, role: string, dryRun: boolean,
                                      options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/role/`, {
    method: 'PATCH', headers, body: JSON.stringify({ role, dry_run: dryRun }),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(body.error || `Action failed: ${res.status}`) as Error & { code?: string }
    err.code = body.code || ''
    throw err
  }
  return body as { id: number; from: string; to: string; dry_run: boolean
                   consequence: 'finance_check_on' | 'finance_check_off' | null
                   /** #39 S4: a saved custom set of permissions goes back to the new preset. */
                   permissions_reset?: boolean
                   /** #39 S4 review fix 4: the editor's consequence codes for this switch. */
                   consequences?: string[] }
}

/** What one person may do, as the editor reads it (request #39 Sprint 4). `keys` are the switches
 *  the editor may show, in the server's catalogue order; `editable` is false for a row nobody edits
 *  (an organisation admin, a super, a partner, your own). */
export interface StaffPermissionsView {
  id: number
  name: string
  role: string
  is_active: boolean
  editable: boolean
  preset: string[]
  permissions: string[]
  custom: boolean
  keys: string[]
  /** The person page's header (Team → a person → Permissions, 2026-10-22). Optional: a payload from
   *  an api deployed a few minutes behind this page omits them, and the page must still draw. */
  email?: string
  created_at?: string
  /** False = no sign-in RECORDED yet (an invitee), never proof they have not come. */
  signed_in?: boolean
  paused?: boolean
  /** The latest changes, newest first (the server caps the list). */
  history?: StaffPermissionChangeRow[]
}

/** One recorded change of somebody's permissions. `kind: 'role_change'` = a Change role put the set
 *  back to the new role's preset. ⚠ `by_super` with a blank `by` is a change made by the HalaTuju
 *  team: the server never hands a super's address to an organisation, so the screen names the team. */
export interface StaffPermissionChangeRow {
  kind: 'edit' | 'role_change' | string
  role: string
  before: string[]
  after: string[]
  added: string[]
  removed: string[]
  at: string
  by: string
  by_super: boolean
}

/** The server's answer to a save or a dry run: the set it would hold, what differs from the set it
 *  holds now, and what else the save would do (`consequences`, worded by the screen). */
export interface StaffPermissionsPlan {
  id: number
  role: string
  dry_run: boolean
  changed: boolean
  permissions: string[]
  custom: boolean
  added: string[]
  removed: string[]
  consequences: string[]
}

export async function getStaffPermissions(adminId: number, options?: ApiOptions) {
  return adminFetch<StaffPermissionsView>(`/api/v1/admin/admins/${adminId}/permissions/`, options)
}

/** Save a set, or with `dryRun` ask what saving it would do. A refusal throws with the server's
 *  sentence and its `code` (`has_open_cases`, `qc_needs_see_all`, …). */
export async function saveStaffPermissions(adminId: number, permissions: string[], dryRun: boolean,
                                           options?: ApiOptions) {
  return adminMutate<StaffPermissionsPlan>(`/api/v1/admin/admins/${adminId}/permissions/`, 'PATCH',
    { permissions, dry_run: dryRun }, options)
}

export async function revokeAdmin(adminId: number, action: 'revoke' | 'restore', options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/revoke/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ action }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(body.error || `Action failed: ${res.status}`) as Error & { code?: string }
    err.code = body.code || body.error || ''
    throw err
  }
  return res.json()
}

/** Re-send a partner's sign-in details, rotating their temporary password. The new password goes
 *  ONLY to their inbox — it is never returned here. Safe to call any number of times. */
export async function resendAdminInvite(adminId: number, options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/resend/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Resend failed: ${res.status}`)
  }
  return res.json() as Promise<{ message: string; emailed: boolean }>
}

// A temp-password partner sets their OWN password server-side (the service role applies it without
// the re-auth the client updateUser({password}) would demand). Scoped to the caller + must_change_password.
export async function adminSetPassword(password: string, options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/set-password/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Set password failed: ${res.status}`)
  }
  return res.json() as Promise<{ ok: boolean }>
}

export async function inviteAdmin(
  data: {
    email: string
    name: string
    role?: 'admin' | 'partner' | 'reviewer' | 'qc' | 'org_admin' | 'finance'
    org_id?: number
    new_org_name?: string
    new_org_code?: string
    contact_person?: string
    org_phone?: string
  },
  options?: ApiOptions
) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/invite/`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })

  // A refusal throws with the SERVER'S sentence and its `code`. Request #39: an address already on
  // the caller's team is `already_on_team` (named, with where to go); any other existing account is
  // `not_invitable`, one sentence that says nothing about it. Both are served — no string here.
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(body.error || `Invite failed: ${res.status}`) as Error & { code?: string }
    err.code = body.code || ''
    throw err
  }

  // `emailed` matters: the welcome email is the ONLY carrier of the temporary password, so a
  // failed send leaves the new partner with no way in until the owner presses Resend.
  return res.json() as Promise<{
    message: string
    org: string | null
    role: string
    already_registered: boolean
    emailed: boolean
  }>
}

