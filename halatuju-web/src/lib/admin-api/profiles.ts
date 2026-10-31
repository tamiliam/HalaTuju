/**
 * An admin's own profile, and a reviewer's own credentials and language fluency (F6).
 */
import { API_BASE, adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Admin profile ───────────────────────────────────────────────────

export interface AdminProfile {
  id: number
  name: string
  email: string
  is_super_admin: boolean
  org_name: string | null
  org_contact_person: string | null
  org_phone: string | null
}

export async function getAdminProfile(options?: ApiOptions) {
  return adminFetch<AdminProfile>('/api/v1/admin/profile/', options)
}

export async function updateAdminProfile(
  data: { name?: string; org_contact_person?: string; org_phone?: string },
  options?: ApiOptions
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/profile/`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Update failed: ${res.status}`)
  }
  return res.json()
}

// ── Own account, every role (common profile S1, 2026-10-31) ──────────
// `GET admin/me/` — opted in for a SOURCE user too (deny by default), so the shared Profile page
// may call it for every role. Read only; each card saves through its own endpoint.

export interface AdminMe {
  id: number
  name: string
  email: string
  role: string
  is_super: boolean
  /** The B40 tenant this person works within (null for a super or a referral partner). */
  organisation: { id: number; name: string } | null
  /** The referral source a source user signs in for; null for staff. */
  source: { id: number; name: string } | null
  /** A referral partner's own organisation (`PartnerAdmin.org`); null for everyone else. */
  referral_partner: { name: string } | null
  /** `'all'` = every gift the organisation runs; a list = narrowed to these. */
  programmes: { id: number; code: string; name: string }[] | 'all'
  /** The RESOLVED permission keys — the same list `admin/role/` serves. */
  permissions: string[]
  first_seen_at: string | null
  last_seen_at: string | null
  /** Common profile S2 — the person's own card. */
  job_title: string
  about: string
  phone: string
  share_phone_with_team: boolean
  share_phone_with_students: boolean
  /** A ~1-hour signed URL of their photo, or null. */
  photo_url: string | null
}

/** What `PATCH admin/me/` may write (only the keys sent are written). */
export type AdminMeCard = Partial<Pick<AdminMe,
  'name' | 'job_title' | 'about' | 'phone' | 'share_phone_with_team' | 'share_phone_with_students'>>

export async function getAdminMe(lang: string, options?: ApiOptions) {
  return adminFetch<AdminMe>(`/api/v1/admin/me/?lang=${encodeURIComponent(lang)}`, options)
}

/** `PATCH admin/me/` — opted in for a source user. A refusal throws with `code` (and `body.fields`
 *  for `not_editable`): `name_required`, `phone_required`, `about_too_long`, … */
export async function updateAdminMe(data: AdminMeCard, options?: ApiOptions) {
  return adminMutate<AdminMe>('/api/v1/admin/me/', 'PATCH', data, options)
}

/** `POST admin/me/photo/` — one image, multipart. Refusals throw with `code`: `too_large`,
 *  `not_an_image`, `unsupported_type`, `storage_unavailable` (503), … Opted in for a source user. */
export async function uploadAdminPhoto(file: File, options?: ApiOptions) {
  const body = new FormData()
  body.append('photo', file)
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/me/photo/`, { method: 'POST', headers, body })
  const b = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw Object.assign(new Error(b.error || `Upload failed: ${res.status}`),
      { status: res.status, code: b.code || b.error || '' })
  }
  return b as { photo_url: string | null }
}

/** `DELETE admin/me/photo/` — the object, then the path. */
export async function deleteAdminPhoto(options?: ApiOptions) {
  return adminMutate<{ photo_url: null }>('/api/v1/admin/me/photo/', 'DELETE', null, options)
}

/**
 * `POST admin/me/password/` — the signed-in person changes their OWN password; the current one is
 * the proof (checked by the server against Supabase). A refusal throws with `code`:
 * `wrong_current_password`, `password_too_short`, `same_password`, `weak_password`,
 * `no_password_sign_in`, `current_password_required`, `supabase_unavailable` (503), or a 429.
 * Opted in for a source user (common profile S1).
 */
export async function changeOwnPassword(currentPassword: string, newPassword: string, options?: ApiOptions) {
  // `others_signed_out`: false when Supabase could not end the person's OTHER sessions (review M2).
  return adminMutate<{ ok: true; others_signed_out?: boolean }>('/api/v1/admin/me/password/', 'POST',
    { current_password: currentPassword, new_password: newPassword }, options)
}

// ── Reviewer profile (F6) ───────────────────────────────────────────
// A reviewer's own credentials + contact details. Self-scoped endpoint
// (always the calling admin's own row). phone/address are private staff
// PII — reviewer + super only, never exposed to students/sponsors.

export interface ReviewerProfile {
  highest_qualification: string
  university: string
  graduation_year: number | null
  field_of_study: string
  phone: string
  address: string
  street_address: string
  postcode: string
  city: string
  state: string
  english_fluency: LangFluency
  bm_fluency: LangFluency
  tamil_fluency: LangFluency
  /** Common profile S2 (owner, 2026-10-31): ONE optional fourth language, by NAME (Mandarin,
   *  Kadazandusun, Bajau…), and its fluency — both or neither (the server refuses half). It does not
   *  count for the onboarding hold, which still needs English, BM or Tamil. */
  other_language: string
  other_language_fluency: LangFluency
  share_phone_with_students: boolean
  /**
   * Whether this reviewer has stepped back from NEW work.
   *
   * ⚠ Stored on `PartnerAdmin`, NOT on the profile row — assignment reads the admin record, and a
   * second copy here would be a second truth to drift. It rides on this payload because one screen
   * owns "how I take part". `paused_at` is read-only; PATCH `paused` to change it.
   */
  paused: boolean
  paused_at?: string | null
}

export type LangFluency = '' | 'conversational' | 'fluent'

export async function getReviewerProfile(options?: ApiOptions) {
  return adminFetch<ReviewerProfile>('/api/v1/admin/reviewer-profile/', options)
}

export async function updateReviewerProfile(
  data: Partial<ReviewerProfile>,
  options?: ApiOptions
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/reviewer-profile/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Update failed: ${res.status}`)
  }
  return res.json() as Promise<ReviewerProfile>
}

