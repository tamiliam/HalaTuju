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

/** Strip a Malaysian mobile to its local digits (no +60, no leading 0). */
function localMobileDigits(raw: string): string {
  let d = raw.replace(/\D/g, '')
  if (d.startsWith('60')) d = d.slice(2)
  if (d.startsWith('0')) d = d.slice(1)
  return d.slice(0, 10) // local mobile (without 0) is at most 10 digits
}

/** Format a Malaysian mobile's LOCAL part (shown after the "+60" prefix) as
 *  "12-345 6789". Tolerates a pasted +60 or a leading 0. */
export function formatMyMobile(raw: string): string {
  const d = localMobileDigits(raw)
  if (d.length <= 2) return d
  const rest = d.slice(2)
  if (rest.length <= 3) return `${d.slice(0, 2)}-${rest}`
  if (d.length <= 9) return `${d.slice(0, 2)}-${rest.slice(0, 3)} ${rest.slice(3)}`
  return `${d.slice(0, 2)}-${rest.slice(0, 4)} ${rest.slice(4)}`
}

/** Valid Malaysian mobile (local form, after "+60"): starts with 1, 9–10 digits
 *  total — i.e. 01X-XXX XXXX entered without the leading 0. */
export function isValidMyMobile(raw: string): boolean {
  return /^1[0-9]{8,9}$/.test(localMobileDigits(raw))
}

// --- International phone (sponsors may be overseas; country picked separately) ---
import { countryByDial, DEFAULT_COUNTRY_ISO } from './countries'

/** The national part of an international number: digits only, no leading 0, capped
 *  so country-code + number stays within E.164's 15-digit limit. */
export function formatIntlPhone(raw: string): string {
  return (raw || '').replace(/\D/g, '').replace(/^0+/, '').slice(0, 14)
}

/** A plausible national number: 4–14 digits (country code added separately). We stay
 *  lenient on purpose — numbering plans vary and the number isn't SMS-verified. */
export function isValidIntlPhone(raw: string): boolean {
  return /^[0-9]{4,14}$/.test((raw || '').replace(/\D/g, ''))
}

/** Compose the stored value: "+<dial> <national>" (e.g. "+60 123456789"). */
export function toStoredPhone(dial: string, localRaw: string): string {
  return `+${dial} ${(localRaw || '').replace(/\D/g, '')}`
}

/** Split a stored phone back into (country iso, national digits) for pre-fill.
 *  A "+"-prefixed value is matched by dial code; anything else is treated as a
 *  bare Malaysian number (all legacy sponsors are +60). */
export function parseStoredPhone(stored: string): { iso: string; local: string } {
  const s = (stored || '').trim()
  if (s.startsWith('+')) {
    const digits = s.slice(1).replace(/\D/g, '')
    const c = countryByDial(digits)
    if (c) return { iso: c.iso2, local: digits.slice(c.dial.length) }
  }
  return { iso: DEFAULT_COUNTRY_ISO, local: s.replace(/\D/g, '').replace(/^60/, '').replace(/^0+/, '') }
}

/** "How did you find us?" — fixed source codes; labels resolved via i18n. */
export const SPONSOR_SOURCES = [
  'search', 'social', 'friend', 'news', 'event', 'organisation', 'other',
] as const

export type SponsorSource = typeof SPONSOR_SOURCES[number]
