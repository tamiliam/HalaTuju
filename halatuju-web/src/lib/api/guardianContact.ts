/**
 * The student's parent/guardian contact (request #26) — the name and phone they gave when applying,
 * which is the number the bursary-signing PIN is later sent to.
 *
 * The student may correct it themselves EXCEPT while bursary signing is possible for them
 * (`guardian_contact_locked`); the server refuses a save then with `err.code ===
 * 'guardian_contact_locked'`. It is shown only to a student who has applied
 * (`has_scholarship_application`). The admin's correction is in `admin-api/applications.ts`.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

export interface GuardianContact {
  has_scholarship_application: boolean
  guardian_contact_locked: boolean
  name: string
  phone: string
}

export async function getGuardianContact(options?: ApiOptions): Promise<GuardianContact> {
  return apiRequest('/api/v1/scholarship/guardian-contact/', options)
}

/** Refusals arrive as `err.code`: `guardian_contact_locked`, `no_application`,
 *  `guardian_name_required`, `guardian_name_too_long`, `guardian_phone_invalid`. */
export async function updateGuardianContact(
  body: { name: string; phone: string }, options?: ApiOptions,
): Promise<GuardianContact & { changed: boolean }> {
  return apiRequest('/api/v1/scholarship/guardian-contact/', {
    method: 'PUT',
    body: JSON.stringify(body),
    ...options,
  })
}
