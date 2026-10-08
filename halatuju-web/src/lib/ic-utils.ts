/**
 * Malaysian NRIC utilities.
 * Format: YYMMDD-SS-NNNN
 */

// Valid Malaysian place-of-birth codes (digits 7-8). ⚠ EVERY STATE CODE, 01-16 and 21-59
// (request #31 review, 2026-10-08): this stopped at 24, so a real IC born in Sabah under 47-49 —
// or anywhere under 25-59 — was refused before it reached the server. Plus 71/72 (abroad) and 82
// (unknown), as before. drift-test: halatuju-web/src/lib/__tests__/icStateCodesDrift.test.ts
export const VALID_STATE_CODES = new Set([
  '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
  '11', '12', '13', '14', '15', '16',
  '21', '22', '23', '24', '25', '26', '27', '28', '29', '30',
  '31', '32', '33', '34', '35', '36', '37', '38', '39', '40',
  '41', '42', '43', '44', '45', '46', '47', '48', '49', '50',
  '51', '52', '53', '54', '55', '56', '57', '58', '59',
  '71', '72', // born abroad
  '82', // unknown
])

/** Strip dashes from NRIC string */
export function stripDashes(value: string): string {
  return value.replace(/-/g, '')
}

/** Format raw digits as XXXXXX-XX-XXXX */
export function formatIc(digits: string): string {
  const d = digits.replace(/\D/g, '').slice(0, 12)
  if (d.length <= 6) return d
  if (d.length <= 8) return `${d.slice(0, 6)}-${d.slice(6)}`
  return `${d.slice(0, 6)}-${d.slice(6, 8)}-${d.slice(8)}`
}

/** Mask NRIC for display: ****-**-1234 */
export function maskIc(nric: string): string {
  const digits = stripDashes(nric)
  if (digits.length < 12) return nric
  return `****-**-${digits.slice(8)}`
}

/** Validate NRIC. Returns error message or null if valid. */
export function validateIc(value: string): string | null {
  const digits = stripDashes(value).replace(/\D/g, '')

  if (digits.length !== 12) {
    return 'IC number must be 12 digits'
  }

  // Parse DOB (YYMMDD)
  const yy = parseInt(digits.slice(0, 2), 10)
  const mm = parseInt(digits.slice(2, 4), 10)
  const dd = parseInt(digits.slice(4, 6), 10)

  // Century: 00-11 = 2000s, 12-99 = 1900s (for student age 15-23 in 2026)
  const year = yy <= 11 ? 2000 + yy : 1900 + yy

  // Basic date validity
  if (mm < 1 || mm > 12 || dd < 1 || dd > 31) {
    return 'Invalid date of birth in IC number'
  }

  // Check the date actually exists
  const dob = new Date(year, mm - 1, dd)
  if (dob.getFullYear() !== year || dob.getMonth() !== mm - 1 || dob.getDate() !== dd) {
    return 'Invalid date of birth in IC number'
  }

  // Age check: must be 15-23 (current year = 2026)
  const currentYear = new Date().getFullYear()
  const age = currentYear - year
  if (age < 15 || age > 23) {
    return 'IC number must belong to a student aged 15\u201323'
  }

  // State code check
  const stateCode = digits.slice(6, 8)
  if (!VALID_STATE_CODES.has(stateCode)) {
    return 'Invalid state code in IC number'
  }

  return null
}
