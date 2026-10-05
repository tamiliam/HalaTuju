/**
 * The parent/guardian phone on the profile and the admin correction (request #26).
 *
 * This number is where the bursary-signing PIN goes, so it must be a Malaysian MOBILE — a landline
 * cannot receive the SMS. The server applies the same rule (`guardian_contact.malaysian_mobile`,
 * review F5) and stores `01X-XXX XXXX`. The apply form keeps the looser `isValidPhone`.
 */
import { formatPhone } from '@/lib/scholarship'

/** Digits in their LOCAL form: `+60…`, `60…` and `0060…` become `0…` (review F4 — a stored
 *  `+60123456789` used to pre-fill as `601-…`, which the validator then refused). */
function localDigits(raw: string): string {
  let d = raw.replace(/\D/g, '')
  if (d.startsWith('0060')) d = '0' + d.slice(4)
  else if (d.startsWith('60')) d = '0' + d.slice(2)
  return d
}

/** A stored or typed number in the editor's display form, e.g. `012-345 6789`. */
export function toLocalPhone(raw: string): string {
  return formatPhone(localDigits(raw || ''))
}

/** A Malaysian mobile: `011` + 8 digits, any other `01X` + 7. Only digits, spaces, dashes and one
 *  leading `+` may be typed — the server refuses anything else. */
export function isValidMobile(raw: string): boolean {
  if (!/^\+?[\d\s-]+$/.test((raw || '').trim())) return false
  const d = localDigits(raw)
  return d.startsWith('01') && d.length === (d.startsWith('011') ? 11 : 10)
}
