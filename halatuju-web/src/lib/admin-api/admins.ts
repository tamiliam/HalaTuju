/**
 * The staff of an organisation: who they are, inviting one, revoking one, resending an
 * invitation, and setting a password.
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (168-218, 284-352, 821-862). The invitation READER
 * (`./invitations`) was written in the middle of them, and `inviteAdmin` 500 lines later.
 */
import { API_BASE, adminFetch } from './client'
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
  /** Whether this account may be DELETED outright rather than only revoked: an admin-shaped role
   *  with NO recorded work. Reviewers are never deletable (owner, 2026-09-09). */
  deletable?: boolean
  /** What this person has DONE, `{what: count}`, empty when nothing. The reason a delete is
   *  refused, so the screen can name it instead of greying a button for no visible cause. */
  work?: Record<string, number>
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
  return res.json() as Promise<{ message: string }>
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

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Invite failed: ${res.status}`)
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

