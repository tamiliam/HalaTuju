/**
 * The referral organisations a student arrives through, and the witness assignment that
 * belongs to the same go-live transition.
 *
 * ⚠ TWO SPANS of the old `admin-api.ts` (442-513 and 812-820).
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Invite / Orgs ───────────────────────────────────────────────────

export interface OrgItem {
  id: number
  code: string
  name: string
  contact_person: string
  phone: string
}

export async function getOrgs(options?: ApiOptions) {
  return adminFetch<{ orgs: OrgItem[] }>('/api/v1/admin/orgs/', options)
}

// ── Sources (referral organisations) + witness assignment (go-live transition) ──
// The Sources registry reuses PartnerOrganisation.phone / contact_person / contact_email
// (NOT a separate contact_phone column). super/org_admin only.

export interface SourceItem {
  id: number
  code: string
  name: string
  contact_person: string
  contact_email: string
  phone: string
  show_in_apply: boolean
  /**
   * Which gift's apply form lists this source. **NULL = every gift** (what all seven live
   * sources carry).
   *
   * ⚠ IT RECORDS INTENT AND CHANGES NOTHING A STUDENT SEES — yet. The apply form's
   * referring-organisation list is still the hard-coded `REFERRING_ORG_OPTIONS` constant in
   * `lib/scholarship.ts`; nothing on the student side reads `show_in_apply`, let alone this.
   * Wiring the form to the registry is its own change.
   */
  programme_id: number | null
  programme_name: string
  is_active: boolean
  student_count: number | null
}

export async function getSources(options?: ApiOptions) {
  return adminFetch<{
    sources: SourceItem[]
    /** Active gifts, for the per-source picker. */
    programmes: Array<{ id: number; code: string; name: string }>
  }>('/api/v1/admin/scholarship/sources/', options)
}

export async function createSource(
  data: {
    code: string; name: string; contact_person?: string; contact_email?: string
    phone?: string; show_in_apply?: boolean
  },
  options?: ApiOptions,
) {
  return adminMutate<SourceItem>('/api/v1/admin/scholarship/sources/', 'POST', data, options)
}

export async function updateSource(
  id: number,
  data: Partial<{
    name: string; contact_person: string; contact_email: string; phone: string
    show_in_apply: boolean; is_active: boolean
    /** null clears it, and clearing means EVERY gift. */
    programme_id: number | null
  }>,
  options?: ApiOptions,
) {
  return adminMutate<SourceItem>(`/api/v1/admin/scholarship/sources/${id}/`, 'PATCH', data, options)
}

/** Assign (code/id) or clear (null) the witness-organisation override for an application. */
export async function assignWitness(
  applicationId: number, witnessOrg: string | number | null, options?: ApiOptions,
) {
  return adminMutate<{ id: number; witness_org: string | null; witness_org_name: string | null }>(
    `/api/v1/admin/scholarship/applications/${applicationId}/witness/`, 'PATCH',
    { witness_org: witnessOrg }, options)
}

