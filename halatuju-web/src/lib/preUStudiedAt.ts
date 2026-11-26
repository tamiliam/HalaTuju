/**
 * "Pre-U institution" — where a student COMPLETED their STPM, Matriculation, Asasi or Diploma
 * (pre-U sprint, 2026-11-26). The profile's `pre_u_studied_at`.
 *
 * ⚠ NOT `pre_u_institution`. That one is the DESTINATION (the college or Form 6 school they are
 * going to, written by the pathway picker); this one is where they STUDIED. Neither the pathway
 * nor the verdict engine reads this field.
 *
 * The rules here are the browser's only: when the field shows and the STPM prefill. The prefill
 * (owner ruling TD-734, 2026-11-25: for an STPM student the typed `pre_u_institution` is the Form
 * 6 school they ATTENDED) is only SHOWN in the box; it is saved only when the student saves the
 * form it sits in. No data is back-filled.
 *
 * ⚠ Only these two first-load rules live here. The field's chips and lists are `lib/preULists.ts`
 * (why: the note at its top — `/scholarship/apply`'s first-load budget).
 */
import { isTertiary } from '@/lib/qualification'

/** Shown only to a student holding STPM, Matriculation, Asasi or Diploma results. */
export function showsPreUStudiedAt(resultsHeld: unknown): boolean {
  return isTertiary(resultsHeld)
}

/** What the box shows: the stored value, else (STPM only) the attended Form 6 school (TD-734). */
export function preUStudiedAtPrefill(profile?: {
  results_held?: string | null
  pre_u_studied_at?: string | null
  pre_u_institution?: string | null
} | null): string {
  const stored = (profile?.pre_u_studied_at || '').trim()
  if (stored) return stored
  return profile?.results_held === 'stpm' ? (profile?.pre_u_institution || '').trim() : ''
}
