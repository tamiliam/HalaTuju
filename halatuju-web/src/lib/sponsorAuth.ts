/**
 * Pure helpers for the sponsor registration form — unit-testable in node-env jest
 * (no DOM). Keep all logic here so the page component stays a thin renderer.
 */

export interface PasswordChecks {
  minLength: boolean   // >= 8 characters
  mixedCase: boolean   // at least 1 uppercase AND 1 lowercase
  hasNumber: boolean   // at least 1 digit
  allPass: boolean
}

/** Evaluate a password against the displayed rules. */
export function checkPassword(pw: string): PasswordChecks {
  const minLength = pw.length >= 8
  const mixedCase = /[a-z]/.test(pw) && /[A-Z]/.test(pw)
  const hasNumber = /[0-9]/.test(pw)
  return { minLength, mixedCase, hasNumber, allPass: minLength && mixedCase && hasNumber }
}

/** "How did you find us?" — fixed source codes; labels resolved via i18n. */
export const SPONSOR_SOURCES = [
  'search', 'social', 'friend', 'news', 'event', 'organisation', 'other',
] as const

export type SponsorSource = typeof SPONSOR_SOURCES[number]
