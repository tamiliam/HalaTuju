/**
 * The student's own profile: reading it, writing it, claiming an NRIC, verifying a phone or
 * an e-mail address, and the one-shot sync from the onboarding wizard.
 *
 * ⚠ THREE SPANS of the old `api.ts` (52-138, 375-456, 636-670). `StudentProfile` sat at the
 * top with the other types and its functions 240 lines below; nothing but authoring order
 * put them apart.
 */
import type { ClaimChannel } from '@/lib/profileClaim'

import { apiRequest } from './client'
import type { ApiOptions } from './client'

// Types
export interface StudentProfile {
  grades: Record<string, string>
  gender: 'male' | 'female'
  nationality: 'malaysian' | 'non_malaysian'
  colorblind?: boolean
  disability?: boolean
  coq_score?: number
  student_merit?: number
  student_signals?: Record<string, number>
  preferred_state?: string
  preferred_call_language?: string
  referral_source?: string
  nric_verified?: boolean
  identity_verified?: boolean   // name + IC confirmed by the MyKad scan, or admin-locked
  // ⚠ THE PADLOCK KEYS ON `nric_locked`, NEVER ON `identity_verified`. They are not
  // interchangeable: `identity_verified` is a display badge that also greens for a card
  // matching but not yet locked (e.g. never scored for genuineness), and it is DERIVED on
  // every read — so a student deleting their card would un-green it. `nric_locked` is the
  // stored, one-way lock. Wiring the padlock to the badge would lock people with no
  // genuineness check and then unlock them again when they removed the evidence.
  nric_locked?: boolean
  // What the uploaded card disagrees with, as codes the screen turns into copy. Never assert
  // which side is wrong — our OCR mangles names too (see apps #27 and #118).
  ic_flags?: string[]
  ic_card_nric?: string
  ic_card_name?: string
  name?: string
  school?: string
  nric?: string
  address?: string
  postal_code?: string
  city?: string
  email?: string
  angka_giliran?: string
  contact_email?: string
  contact_email_verified?: boolean
  contact_phone?: string
  contact_phone_verified?: boolean
  phone_verify_enabled?: boolean   // student phone-verify control live? (paused by default — cost)
  whatsapp_opt_in?: boolean
  exam_type?: 'spm' | 'stpm'
  /** Which exam's results were last COMPLETED — '' when never recorded. Not the same
   *  question as `exam_type`, which a card tap sets with no results behind it. */
  results_exam_type?: '' | 'spm' | 'stpm'
  stpm_grades?: Record<string, string>
  stpm_cgpa?: number
  muet_band?: number
  // Financial detail — canonical home for the BrightPath Bursary Programme
  household_income?: number | null
  household_size?: number | null
  receives_str?: boolean
  receives_jkm?: boolean
  guardians?: { name?: string; phone?: string; relationship?: string; occupation?: string; income?: number }[]
  // TD-063: the SPM subjects the student studied as their stream/aliran. When
  // present, the merit engine uses these for the 30% Sec2 weight instead of
  // guessing the stream from the pools. Sent through to /eligibility/check/.
  stream_subjects?: string[]
  // The SPM subjects picked as electives/tambahan — the durable record of which
  // grade keys are electives, so the grades form survives a logout/login. Up to 7.
  elective_subjects?: string[]
  // Structured family roster (profile-level home; two-way synced with an open
  // application). Same field names as ScholarshipApplication's roster columns.
  father_name?: string
  father_occupation?: string
  father_occupation_other?: string
  mother_name?: string
  mother_occupation?: string
  mother_occupation_other?: string
  other_family_members?: { role: 'brother' | 'sister' | 'guardian'; occupation: string; occupation_other?: string }[]
  siblings_in_school?: number | null
  siblings_in_tertiary?: number | null
  // Pathway / "Your Plans" (profile-level home; two-way synced with an open application)
  pathway_certainty?: string
  chosen_pathway?: string
  pre_u_track?: string          // STPM stream / Matric track, when applicable
  pre_u_institution?: string
  chosen_programme?: Record<string, unknown>   // stored snake: {course_id, course_name, field_key}
  pathways_considered?: string[]
  uncertainty_reasons?: string[]
  uncertainty_note?: string
  // Application Tracking surfaces (read-only on /profile)
  merit_score?: number | null   // SPM academic merit, computed from grades
  pathway?: string              // back-compat alias of chosen_pathway
  application_open?: boolean     // is the family/pathway link currently live (app undecided)
}

// TD-254. ⚠ `exists` NO LONGER CARRIES A NAME — only the challenge CHANNELS; `confirm: true` is
// gone (it moved the profile's primary key in raw SQL) and the server refuses it. A claim runs
// through the two calls below; a refusal is a non-2xx whose `code` `apiRequest` puts on the Error.
export async function claimNric(
  nric: string,
  confirm: boolean = false,
  options?: ApiOptions
): Promise<{ status: 'created' | 'exists' | 'linked'; channels?: ClaimChannel[] }> {
  return apiRequest('/api/v1/profile/claim-nric/', {
    method: 'POST',
    body: JSON.stringify({ nric, confirm }),
    ...options,
  })
}

export async function sendClaimCode(
  nric: string, channel: ClaimChannel, lang: string, options?: ApiOptions
): Promise<{ status: string; channel: ClaimChannel }> {
  return apiRequest('/api/v1/profile/claim-nric/send-code/', {
    method: 'POST', body: JSON.stringify({ nric, channel, lang }), ...options,
  })
}

export async function confirmClaimCode(
  nric: string, code: string, options?: ApiOptions
): Promise<{ status: string }> {
  return apiRequest('/api/v1/profile/claim-nric/confirm-code/', {
    method: 'POST', body: JSON.stringify({ nric, code }), ...options,
  })
}

export async function sendVerificationEmail(
  email: string,
  lang?: string,
  options?: ApiOptions
): Promise<{ status: string }> {
  return apiRequest('/api/v1/profile/verify-email/send/', {
    method: 'POST',
    body: JSON.stringify({ email, lang }),
    ...options,
  })
}

// Phone verification over WhatsApp via Twilio Verify (S4 / TD-136). Opt-in / voluntary.
export async function sendPhoneVerification(
  phone?: string,
  options?: ApiOptions
): Promise<{ status: string }> {
  return apiRequest('/api/v1/profile/verify-phone/send/', {
    method: 'POST',
    body: JSON.stringify(phone ? { phone } : {}),
    ...options,
  })
}

export async function checkPhoneVerification(
  code: string,
  phone?: string,
  options?: ApiOptions
): Promise<{ verified: boolean; error?: string }> {
  return apiRequest('/api/v1/profile/verify-phone/check/', {
    method: 'POST',
    body: JSON.stringify(phone ? { code, phone } : { code }),
    ...options,
  })
}

export async function getProfile(options?: ApiOptions): Promise<StudentProfile> {
  return apiRequest('/api/v1/profile/', options)
}

export async function updateProfile(
  profile: Partial<StudentProfile>,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest('/api/v1/profile/', {
    method: 'PUT',
    body: JSON.stringify(profile),
    ...options,
  })
}

// Profile sync (after first login — pushes localStorage data to backend)
export interface SyncProfileData {
  grades?: Record<string, string>
  gender?: string
  nationality?: string
  colorblind?: boolean
  disability?: boolean
  student_signals?: Record<string, Record<string, number>>
  preferred_state?: string
  name?: string
  school?: string
  nric?: string
  referral_source?: string
  exam_type?: string
  /** Set by a results editor on COMPLETION only; the server drops it if unbacked. */
  results_exam_type?: string
  stpm_grades?: Record<string, string>
  stpm_cgpa?: number
  muet_band?: number
  coq_score?: number
  stream_subjects?: string[]
  elective_subjects?: string[]
}

export async function syncProfile(
  data: SyncProfileData,
  options?: ApiOptions
): Promise<{ message: string; created: boolean }> {
  return apiRequest('/api/v1/profile/sync/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}

