import type { ReviewerProfile } from '@/lib/admin-api'

/**
 * Client mirror of the backend `reviewer_onboarding.reviewer_profile_complete` — which compulsory
 * reviewer fields are still missing. The BACKEND flag (on GET /api/v1/admin/role/) is the real
 * gate; this mirror only paints `*` markers + the "still needed" banner + decides the redirect
 * after a completing save. Keep the two in step (owner set: credentials + one language + phone,
 * plus the PartnerAdmin name).
 *
 * Returns field keys (not labels); the profile page maps them to i18n. Empty = complete.
 */
export const REQUIRED_REVIEWER_FIELDS = [
  'name', 'highest_qualification', 'university', 'graduation_year',
  'field_of_study', 'languages', 'phone',
] as const

const filled = (v?: string | null) => !!(v && String(v).trim())
const speaks = (v?: string) => v === 'conversational' || v === 'fluent'

export function missingReviewerFields(name: string, rp: ReviewerProfile | null): string[] {
  const m: string[] = []
  if (!name.trim()) m.push('name')
  if (!filled(rp?.highest_qualification)) m.push('highest_qualification')
  if (!filled(rp?.university)) m.push('university')
  if (!rp?.graduation_year) m.push('graduation_year')
  if (!filled(rp?.field_of_study)) m.push('field_of_study')
  if (!speaks(rp?.english_fluency) && !speaks(rp?.bm_fluency) && !speaks(rp?.tamil_fluency)) {
    m.push('languages')
  }
  if (!filled(rp?.phone)) m.push('phone')
  return m
}

export const reviewerProfileComplete = (name: string, rp: ReviewerProfile | null): boolean =>
  missingReviewerFields(name, rp).length === 0
