// Structured family roster (the "About your family" redesign, 2026-06).
// Mirrors halatuju_api/apps/scholarship/family.py — keep the codes IN SYNC.
// Labels are i18n keys (`scholarship.family.profession.<code>`), rendered by the
// form; this module is just codes, groups, and the pure helpers.

export type ProfessionCode = string

export type FamilyRole = 'brother' | 'sister' | 'guardian'

export interface OtherMember {
  role: FamilyRole
  occupation: ProfessionCode
  occupation_other?: string
}

// Grouped for the dropdown's <optgroup>s. Order + codes match family.py exactly.
export const PROFESSION_GROUPS: { groupKey: string; codes: ProfessionCode[] }[] = [
  {
    groupKey: 'employed',
    codes: [
      'gov', 'professional', 'teacher', 'uniform', 'healthcare', 'factory',
      'technician', 'clerk', 'private', 'retail', 'storekeeper', 'fnb',
      'security', 'cleaner', 'maintenance', 'plantation',
    ],
  },
  {
    groupKey: 'informal',
    codes: [
      'hawker', 'farmer', 'smallholder', 'fisherman', 'livestock', 'ehailing',
      'driver', 'construction', 'supervisor', 'mechanic', 'craft', 'hairdresser',
      'tuition', 'caregiver', 'agent', 'odd_jobs', 'self_employed',
    ],
  },
  {
    groupKey: 'other',
    codes: ['homemaker', 'retired', 'unemployed', 'unable', 'deceased', 'no_contact', 'other'],
  },
]

export const PROFESSION_CODES: ProfessionCode[] = PROFESSION_GROUPS.flatMap((g) => g.codes)

export const FAMILY_ROLES: FamilyRole[] = ['brother', 'sister', 'guardian']

// Professions that do NOT earn income — mirror of family.NON_EARNING. Used to
// prefill the income wizard's "who works" select from the roster.
export const NON_EARNING: ReadonlySet<ProfessionCode> = new Set([
  'homemaker', 'retired', 'unemployed', 'unable', 'deceased', 'no_contact',
])

export const MAX_OTHER_MEMBERS = 6

/** First-in-family is a CONSEQUENCE, not a toggle: true iff no sibling is in (or
 * through) tertiary education — the "in college or university" count. */
export function derivedFirstInFamily(siblingsInTertiary: number | null | undefined): boolean {
  return (siblingsInTertiary || 0) === 0
}

export interface RosterEarnerInput {
  father_occupation?: ProfessionCode
  mother_occupation?: ProfessionCode
  other_family_members?: OtherMember[]
}

/** Member roles whose profession earns income — the prefill default for the income
 * wizard's "who is working" select (so the student doesn't re-name the same people).
 * Roles use the income wizard's vocabulary: father/mother/guardian/brother/sister. */
export function earningMembers(roster: RosterEarnerInput): string[] {
  const out: string[] = []
  if (roster.father_occupation && !NON_EARNING.has(roster.father_occupation)) out.push('father')
  if (roster.mother_occupation && !NON_EARNING.has(roster.mother_occupation)) out.push('mother')
  for (const m of roster.other_family_members ?? []) {
    if (m && FAMILY_ROLES.includes(m.role) && m.occupation && !NON_EARNING.has(m.occupation) && !out.includes(m.role)) {
      out.push(m.role)
    }
  }
  return out
}

/** Order-independent equality of two member lists — used to decide whether the income
 *  wizard's roster-derived default actually needs re-seeding (avoids a render loop). */
export function sameMemberSet(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false
  const sa = new Set(a)
  return b.every((m) => sa.has(m))
}

/** Normalise the member pool to safe shapes (drops malformed, caps length). */
export function cleanOtherMembers(raw: unknown): OtherMember[] {
  if (!Array.isArray(raw)) return []
  const out: OtherMember[] = []
  for (const m of raw.slice(0, MAX_OTHER_MEMBERS)) {
    if (!m || typeof m !== 'object') continue
    const role = (m as OtherMember).role
    const occ = (m as OtherMember).occupation
    if (!FAMILY_ROLES.includes(role) || !PROFESSION_CODES.includes(occ)) continue
    const entry: OtherMember = { role, occupation: occ }
    const other = ((m as OtherMember).occupation_other || '').trim().slice(0, 120)
    if (occ === 'other' && other) entry.occupation_other = other
    out.push(entry)
  }
  return out
}

// A person's NAME may contain letters, spaces, and the connectors that appear in Malaysian names:
// "/" (A/L, A/P, S/O, D/O), "@" (alias — "SITI @ AISHAH"), plus initials (.), apostrophes (D'CRUZ)
// and hyphens (NUR-AIN). It must contain NO digits — an IC / phone typed into a name box is exactly
// the error this guards against (a real case: a father_name stored as an IC number). Mirrors
// family.is_valid_person_name in the backend — keep IN SYNC.
const PERSON_NAME_RE = /^[A-Za-z][A-Za-z\s./@'-]*$/

export function isValidPersonName(name: string | null | undefined): boolean {
  const t = (name || '').trim()
  return t === '' || PERSON_NAME_RE.test(t)   // empty is "not invalid" — required-ness is separate
}
