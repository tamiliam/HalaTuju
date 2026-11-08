/**
 * Request #26: the parent/guardian contact calls on a bursary application (correct the number,
 * record a call). Split out of `applications.ts` to keep it under the 600-line file rule; it
 * re-exports everything here, so `from './applications'` still works.
 */
import { adminMutate } from './client'
import type { ApiOptions } from './client'

/** Request #26: correct the parent/guardian contact of the student behind this application.
 *  Super + org_admin only (403 otherwise; 404 across organisations). Allowed at ANY time,
 *  including while the student is locked out because bursary signing is possible, and every
 *  real change is recorded server-side. `changed: false` means the values were already these. */
export async function correctGuardianContact(
  id: number, body: { name: string; phone: string }, options?: ApiOptions,
) {
  return adminMutate<{ name: string; phone: string; changed: boolean }>(
    `/api/v1/admin/scholarship/applications/${id}/guardian-contact/`, 'POST', body, options)
}

export type GuardianCallOutcome =
  'shared_confirmed' | 'parent_number_confirmed' | 'parent_number_corrected' | 'could_not_reach'

/** Request #26 (consent framing): "Record call" — an admin's call to the parent, on the record.
 *  Super + org_admin only, the correction's fence. `parent_number_corrected` also STORES `number`
 *  as the parent phone; every other outcome is about the number on file (send `number: ''`).
 *  `consent` is null for could_not_reach. `needs_call` is the live flag after the call. */
export async function recordGuardianCall(
  id: number,
  body: { outcome: GuardianCallOutcome; consent: boolean | null; number: string; parent_name: string; note: string },
  options?: ApiOptions,
) {
  return adminMutate<{ id: number; outcome: GuardianCallOutcome; name: string; phone: string; needs_call: boolean }>(
    `/api/v1/admin/scholarship/applications/${id}/guardian-call/`, 'POST', body, options)
}
