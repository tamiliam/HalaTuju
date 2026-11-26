/**
 * The Angka Giliran (exam index number) — its two shapes and the ONE normaliser (pre-U sprint,
 * 2026-11-26). The twin of the API's `apps/courses/angka_giliran.py`: same shapes, same rule
 * (upper case, every space removed), same 11-character length.
 *
 *  - SPM:  AB123C456   (two letters, three digits, a letter, three digits)
 *  - STPM: AB1234/5678 (two letters, four digits, a slash, four digits)
 */
export const ANGKA_GILIRAN_MAX = 11
const SPM_RE = /^[A-Z]{2}\d{3}[A-Z]\d{3}$/
const STPM_RE = /^[A-Z]{2}\d{4}\/\d{4}$/

/** Upper case, every whitespace character removed, cut to the column's 11 characters. */
export function normaliseAngkaGiliran(value: string): string {
  return (value || '').replace(/\s+/g, '').toUpperCase().slice(0, ANGKA_GILIRAN_MAX)
}

/** True for a blank value (the field is optional) or either shape. */
export function isValidAngkaGiliran(value: string): boolean {
  const v = (value || '').replace(/\s+/g, '').toUpperCase()
  return v === '' || SPM_RE.test(v) || STPM_RE.test(v)
}
