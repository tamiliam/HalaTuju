/**
 * B40 Assistance Programme — pure form helpers.
 *
 * Logic lives here (node-testable) so the page component stays a thin renderer.
 */
import type { StudentProfile, ScholarshipApplication, EligibleCourse, PathwayResult, StpmEligibleCourse } from '@/lib/api'

// SPM grades that count as an "A" for the shortlist (A+, A and A- all count,
// matching the backend's count_spm_a_grades and the B40 candidate profiles).
export const A_GRADES = new Set(['A+', 'A', 'A-'])

export function countAGrades(grades?: Record<string, string> | null): number {
  if (!grades) return 0
  return Object.values(grades).filter(
    (g) => typeof g === 'string' && A_GRADES.has(g.trim().toUpperCase())
  ).length
}

export type Qualification = 'spm' | 'stpm'
export type IntendedPathway =
  | '' | 'asasi' | 'matrik' | 'stpm' | 'pismp' | 'diploma' | 'degree' | 'other'

export const PATHWAY_OPTIONS: IntendedPathway[] = [
  'asasi', 'matrik', 'stpm', 'pismp', 'diploma', 'degree', 'other',
]

// Referring-organisation codes (fixed list from the legacy Google Form). Labels
// come from i18n (`scholarship.apply.org.<code>`). A code that matches an active
// PartnerOrganisation row links the FK server-side; the rest are generic sources.
export const REFERRING_ORG_OPTIONS = [
  // Partner organisations (Google-form order)
  'smc', 'cumig', 'ewrf', 'hyo', 'mhm', 'sathya_sai', 'tara', 'hss', 'pptm',
  // Individual coordinators + self-referral + generic catch-alls
  'pushparani', 'govind', 'halatuju', 'social', 'other',
] as const
export type ReferringOrg = typeof REFERRING_ORG_OPTIONS[number] | ''

// Preferred language for phone calls (B40 outreach). Labels via i18n
// (`scholarship.apply.callLang.<code>`); stored on profile.preferred_call_language.
export const CALL_LANGUAGE_OPTIONS = ['en', 'ms', 'ta', 'mixed'] as const
export type CallLanguage = typeof CALL_LANGUAGE_OPTIONS[number] | ''

// Mirrors the onboarding state list (onboarding/profile/page.tsx). Static — a
// fixed set of Malaysian states/federal territories that does not change.
export const MALAYSIAN_STATES = [
  'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan',
  'Pahang', 'Perak', 'Perlis', 'Pulau Pinang', 'Sabah',
  'Sarawak', 'Selangor', 'Terengganu',
  'Kuala Lumpur', 'Labuan', 'Putrajaya',
] as const

// NRIC format XXXXXX-XX-XXXX (the claim endpoint does the full age/state checks).
const NRIC_RE = /^\d{6}-\d{2}-\d{4}$/

/**
 * Format raw NRIC keystrokes/paste into the canonical XXXXXX-XX-XXXX mask:
 * keep digits only, cap at 12, and insert dashes after the 6th and 8th digit.
 * Idempotent — re-running on an already-masked value returns it unchanged — so it
 * can be applied on every onChange. The output is exactly what NRIC_RE expects.
 */
export function formatNric(raw: string): string {
  const d = raw.replace(/\D/g, '').slice(0, 12)
  return [d.slice(0, 6), d.slice(6, 8), d.slice(8, 12)].filter(Boolean).join('-')
}

/**
 * Format raw phone keystrokes/paste into a readable Malaysian style, aware of
 * both mobile and landline numbering (area codes are 2 or 3 digits by region):
 *   012-345 6789 / 011-2345 6789  — mobile (01X)
 *   03-1234 5678                  — Klang Valley
 *   04-123 4567                   — other peninsular (04/05/06/07/09)
 *   088-123 456                   — Sabah/Sarawak (08X)
 * Digits only, capped at 11, idempotent — safe to run on every onChange.
 */
export function formatPhone(raw: string): string {
  const d = raw.replace(/\D/g, '').slice(0, 11)
  if (!d) return ''
  const areaLen = d.startsWith('01') ? 3       // mobile 01X
    : d.startsWith('03') ? 2                    // Klang Valley
    : d.startsWith('08') ? 3                    // Sabah/Sarawak 08X
    : d.startsWith('0') ? 2                     // 04/05/06/07/09 …
    : Math.min(3, d.length)                     // defensive (no leading 0)
  if (d.length <= areaLen) return d
  return `${d.slice(0, areaLen)}-${groupSubscriber(d.slice(areaLen))}`
}

/** Group the subscriber digits (after the area code) for display. */
function groupSubscriber(s: string): string {
  if (s.length <= 5) return s
  if (s.length === 6) return `${s.slice(0, 3)} ${s.slice(3)}`   // 08X landline: 3+3
  if (s.length === 8) return `${s.slice(0, 4)} ${s.slice(4)}`   // 03 / 011: 4+4
  return `${s.slice(0, s.length - 4)} ${s.slice(s.length - 4)}` // else: rest + final 4
}

// A Malaysian phone number is 9–11 digits starting with 0 (mobile 01X… or a
// landline 0X…). We validate on the digits, ignoring the display dashes/spaces.
export function isValidPhone(s: string): boolean {
  return /^0\d{8,10}$/.test(s.replace(/\D/g, ''))
}

// ── Plans redesign: eligible-pathway dropdown (context-aware Plans step) ──
// Display order for the "Sure" branch pathway dropdown (SPM leavers). Mirrors the
// backend pathway_type taxonomy; iljtm/ilkbs are already split server-side.
export const PATHWAY_ORDER = [
  'matric', 'stpm', 'asasi', 'university', 'poly', 'kkom', 'pismp', 'iljtm', 'ilkbs',
] as const
export type PathwayKey = typeof PATHWAY_ORDER[number]

export interface EligiblePathway { key: PathwayKey; count: number }

// Has the student decided on a pathway, or are they still exploring? Drives the
// progressive-disclosure split at the top of the Plans step.
export type PathwayCertainty = '' | 'sure' | 'uncertain'

// ── Plans redesign P3: eligible-programme course picker (the decided course) ──
// Pathways whose "decided" branch is a programme list (→ course combobox). The two
// institution pathways (matric, stpm) take the stream→school / track→college flow (P4).
export const PROGRAMME_PATHWAYS = ['asasi', 'university', 'poly', 'kkom', 'pismp', 'iljtm', 'ilkbs'] as const
export function isProgrammePathway(key: string): boolean {
  return (PROGRAMME_PATHWAYS as readonly string[]).includes(key)
}

/** The single decided programme (Sure branch). Persisted as JSON in `chosen_programme`. */
export interface ChosenProgramme {
  courseId: string
  courseName: string
  fieldKey: string
}

/**
 * The eligible programmes for a chosen pathway: the student's eligible courses
 * (already narrowed by the engine to what their results qualify them for) filtered
 * to that `pathway_type`, sorted alphabetically by name. Feeds the course combobox.
 */
export function programmesForPathway(
  courses: EligibleCourse[] | null | undefined,
  pathwayKey: string,
): EligibleCourse[] {
  if (!courses || !pathwayKey) return []
  return courses
    .filter((c) => c.pathway_type === pathwayKey)
    .sort((a, b) => a.course_name.localeCompare(b.course_name))
}

// ── Plans redesign P4: institution pathways (Matriculation + STPM Form 6) ──
// The two pathways whose decided branch is an institution (track/stream → college/school),
// not a course list. They store onto pre_u_track + pre_u_institution.
export function isInstitutionPathway(key: string): boolean {
  return key === 'matric' || key === 'stpm'
}

// STPM Form 6 streams (fixed). "not_sure" is a valid answer — the student still names a
// school. Keys map to the school data's stream labels (Sains / Sains Sosial).
export const STPM_STREAMS = ['sains', 'sains_sosial', 'not_sure'] as const

/**
 * The matriculation tracks the student qualifies for, from a /calculate/pathways/
 * response — the matric entries flagged eligible, in the engine's order. Track ids
 * (sains/kejuruteraan/sains_komputer/perakaunan) match the college data's track keys.
 */
export function eligibleMatricTracks(pathways: PathwayResult[] | null | undefined): string[] {
  if (!pathways) return []
  return pathways.filter((p) => p.pathway === 'matric' && p.eligible).map((p) => p.trackId)
}

// ── Plans redesign P5: STPM-student degree branch + Uncertain branch ──
// "Where are you right now?" reasons for the Uncertain branch (multi-select, optional).
// Stored in uncertainty_reasons; a coordinator decides mentoring from them (not auto-set).
export const UNCERTAINTY_REASONS = ['exploring', 'results', 'guidance', 'family', 'finance'] as const

/**
 * Map STPM eligible degrees to the course shape <ProgrammePicker> consumes, sorted
 * alphabetically — the university becomes the institution line. Lets the SPM course
 * combobox be reused for the post-STPM-student degree pick (no pathway step for them).
 */
export function stpmDegreesToCourses(degrees: StpmEligibleCourse[] | null | undefined): EligibleCourse[] {
  if (!degrees) return []
  return degrees
    .map((d) => ({
      course_id: d.course_id,
      course_name: d.course_name,
      level: 'Degree',
      field: d.field,
      field_key: d.field_key,
      source_type: 'stpm',
      pathway_type: 'stpm',
      merit_cutoff: null,
      student_merit: null,
      merit_label: null,
      merit_color: null,
      institution_name: d.university,
    } as EligibleCourse))
    .sort((a, b) => a.course_name.localeCompare(b.course_name))
}

/**
 * From an eligibility response's `pathway_stats` ({pathway_type: count}), return the
 * pathways the student qualifies for (count > 0) in a fixed display order, each with
 * its eligible-programme count. Drives the single-select pathway dropdown. Unknown
 * keys (e.g. the un-split 'tvet' fallback) are ignored — only the 9 known pathways show.
 */
export function eligiblePathways(pathwayStats?: Record<string, number> | null): EligiblePathway[] {
  if (!pathwayStats) return []
  const out: EligiblePathway[] = []
  for (const key of PATHWAY_ORDER) {
    const count = pathwayStats[key] || 0
    if (count > 0) out.push({ key, count })
  }
  return out
}

// ── My Plans + My Support (Sprint 10) ────────────────────────────────────
// UPU / destination intent. 'ipts' (IPTS-only) is the engine's disqualifier;
// the form never blocks on it — the backend declines silently (S8 gate).
export type UpuStatus = '' | 'applied' | 'public_other' | 'ipts' | 'unknown'
export const UPU_OPTIONS: Exclude<UpuStatus, ''>[] = ['applied', 'public_other', 'ipts', 'unknown']

// Optional support questions (Yes / No / Not sure).
export type HelpChoice = '' | 'yes' | 'no' | 'unsure'
export const HELP_OPTIONS: Exclude<HelpChoice, ''>[] = ['yes', 'no', 'unsure']

// Other scholarships applied/held → funding-overlap signal (labels via i18n).
export const OTHER_SCHOLARSHIP_OPTIONS = ['jpa', 'khazanah', 'petronas', 'bnm', 'dermasiswa_b40', 'maybank', 'maxis', 'sime_darby', 'other'] as const

// A ranked course choice (rank derived from array order). Sourced from the
// student's saved courses; shape mirrors the backend `top_choices` entries.
export interface TopChoice {
  courseId: string
  courseName: string
  institution: string
}

/**
 * The apply form only carries fields the applicant edits here. Academic data
 * (exam type, grades, STPM CGPA) is read live from the canonical HalaTuju
 * profile — never collected or posted by this form. The financial fields below
 * are written back to the profile on submit (their canonical home).
 */
export interface ApplyFormState {
  // About Me (inline-editable; pre-filled from the profile, committed on submit).
  // NRIC is edited here but saved via the validated claim path, not the payload.
  name: string
  school: string
  nric: string
  referringOrg: ReferringOrg
  homeState: string
  phone: string
  // My Family
  householdIncome: string   // strings for controlled inputs
  householdSize: string
  receivesStr: boolean
  receivesJkm: boolean
  parentName: string
  parentPhone: string
  callLanguage: CallLanguage
  // My Plans
  // Plans redesign: the step opens by asking whether the student has decided on
  // a pathway. 'sure' reveals a single-select eligible-pathway dropdown; 'uncertain'
  // routes to the exploration branch (P5). chosenPathway is a PATHWAY_ORDER key.
  pathwayCertainty: PathwayCertainty
  chosenPathway: string             // PathwayKey when certainty === 'sure'
  chosenProgramme: ChosenProgramme | null  // the single decided course (programme pathways)
  preUTrack: string                 // matric track / STPM stream (institution pathways)
  preUInstitution: string           // matric college / STPM school name
  uncertaintyReasons: string[]      // Uncertain branch — "where are you right now?" (optional)
  uncertaintyNote: string           // Uncertain branch — free text (optional)
  pathwaysConsidered: string[]      // pathway keys (non-exclusive) — Uncertain leanings
  topChoices: (TopChoice | null)[]  // Uncertain STPM students' top-3 degree picks (3 ranked slots; null = empty)
  upuStatus: UpuStatus              // derived from the chosen public pathway
  fieldOfStudy: string              // field-taxonomy key
  otherScholarships: string[]       // scholarship keys
  otherScholarshipsText: string
  intendsTertiary2026: boolean      // engine hard gate — must be true to qualify
  // My Support
  helpUniversity: HelpChoice
  helpScholarship: HelpChoice
  anythingElse: string
  consentToContact: boolean
  declarationName: string   // typed full-name "signature" on the truthfulness declaration
}

export function profileToApplyDefaults(profile?: StudentProfile | null): ApplyFormState {
  // Pre-fill every editable field from the canonical profile. The form holds the
  // edits in state and writes them back only on a successful submit. Academic
  // data (results) is shown read-only by My Results, not carried in this form.
  const guardian = profile?.guardians?.[0]
  return {
    name: profile?.name ?? '',
    school: profile?.school ?? '',
    // Pre-filled values are masked too, so an older unformatted profile value
    // still displays as XXXXXX-XX-XXXX / 0XX-XXX XXXX.
    nric: formatNric(profile?.nric ?? ''),
    referringOrg: (profile?.referral_source as ReferringOrg) ?? '',
    homeState: profile?.preferred_state ?? '',
    phone: formatPhone(profile?.contact_phone ?? ''),
    householdIncome: profile?.household_income != null ? String(profile.household_income) : '',
    householdSize: profile?.household_size != null ? String(profile.household_size) : '',
    receivesStr: !!profile?.receives_str,
    receivesJkm: !!profile?.receives_jkm,
    parentName: guardian?.name ?? '',
    parentPhone: formatPhone(guardian?.phone ?? ''),
    callLanguage: (profile?.preferred_call_language as CallLanguage) ?? '',
    pathwayCertainty: '',
    chosenPathway: '',
    chosenProgramme: null,
    preUTrack: '',
    preUInstitution: '',
    uncertaintyReasons: [],
    uncertaintyNote: '',
    pathwaysConsidered: [],
    topChoices: [],
    upuStatus: '',
    fieldOfStudy: '',
    otherScholarships: [],
    otherScholarshipsText: '',
    intendsTertiary2026: true,
    helpUniversity: '',
    helpScholarship: '',
    anythingElse: '',
    consentToContact: false,
    declarationName: '',   // never pre-filled — the student must actively sign
  }
}

/** A read-only summary of the profile's academic standing, for display only. */
export interface AcademicSummary {
  examType: Qualification
  aCount: number          // SPM A+/A/A- count
  aPlusCount: number      // SPM A+ count, for the "including N A+" line
  stpmCgpa: number | null
  hasData: boolean        // does the profile carry enough academic data to score?
}

export function profileAcademicSummary(profile?: StudentProfile | null): AcademicSummary {
  const examType: Qualification = profile?.exam_type === 'stpm' ? 'stpm' : 'spm'
  const grades = profile?.grades
  const aCount = countAGrades(grades)
  const aPlusCount = grades
    ? Object.values(grades).filter((g) => typeof g === 'string' && g.trim().toUpperCase() === 'A+').length
    : 0
  const stpmCgpa = profile?.stpm_cgpa ?? null
  const hasData = examType === 'stpm'
    ? stpmCgpa != null
    : !!grades && Object.keys(grades).length > 0
  return { examType, aCount, aPlusCount, stpmCgpa, hasData }
}

export interface ApplicationPayload {
  // About Me + My Family profile fields (write-only; synced to the profile
  // server-side). NRIC is NOT here — it goes through the claim path on submit.
  name: string
  school: string
  preferred_state: string
  contact_phone: string
  preferred_call_language: string
  referral_source: string
  guardians: { name: string; phone: string }[]
  household_income: number | null
  household_size: number | null
  receives_str: boolean
  receives_jkm: boolean
  intends_tertiary_2026: boolean
  consent_to_contact: boolean
  // My Plans + My Support (Sprint 10; Plans redesign adds certainty + chosen pathway)
  pathway_certainty: string
  chosen_pathway: string
  chosen_programme: Record<string, unknown>
  pre_u_track: string
  pre_u_institution: string
  uncertainty_reasons: string[]
  uncertainty_note: string
  pathways_considered: string[]
  top_choices: { rank: number; course_id: string; course_name: string; institution: string }[]
  upu_status: string
  field_of_study: string
  other_scholarships: string[]
  other_scholarships_text: string
  help_university: string
  help_scholarship: string
  anything_else: string
  declaration_name: string   // typed signature; declared_at is stamped server-side
  form_data: Record<string, unknown>
}

function toIntOrNull(s: string): number | null {
  const t = s.trim()
  if (t === '') return null
  const n = parseInt(t, 10)
  return Number.isFinite(n) ? n : null
}

export function buildApplicationPayload(form: ApplyFormState): ApplicationPayload {
  // Academic fields are intentionally absent — the backend reads them from the
  // profile. The About Me + My Family fields are synced to the profile
  // server-side. NRIC is committed separately via the validated claim path.
  // Conflict policy for shared profile fields (preferred_state, contact_phone,
  // referral_source, name, school): last write wins. Apply submit overwrites
  // any value the student set earlier via /profile or /onboarding/profile.
  const guardians = form.parentName.trim() || form.parentPhone.trim()
    ? [{ name: form.parentName.trim(), phone: form.parentPhone.trim() }]
    : []
  return {
    name: form.name.trim(),
    school: form.school.trim(),
    preferred_state: form.homeState,
    contact_phone: form.phone.trim(),
    preferred_call_language: form.callLanguage,
    referral_source: form.referringOrg,
    guardians,
    household_income: toIntOrNull(form.householdIncome),
    household_size: toIntOrNull(form.householdSize),
    receives_str: form.receivesStr,
    receives_jkm: form.receivesJkm,
    intends_tertiary_2026: form.intendsTertiary2026,
    consent_to_contact: form.consentToContact,
    // My Plans + My Support — rank is derived from the top-3 selection order.
    pathway_certainty: form.pathwayCertainty,
    chosen_pathway: form.chosenPathway,
    chosen_programme: form.chosenProgramme
      ? { course_id: form.chosenProgramme.courseId, course_name: form.chosenProgramme.courseName, field_key: form.chosenProgramme.fieldKey }
      : {},
    pre_u_track: form.preUTrack,
    pre_u_institution: form.preUInstitution,
    uncertainty_reasons: form.uncertaintyReasons,
    uncertainty_note: form.uncertaintyNote.trim(),
    pathways_considered: form.pathwaysConsidered,
    // Drop empty slots; rank by surviving order (1st/2nd/3rd).
    top_choices: form.topChoices
      .filter((c): c is TopChoice => !!c && !!c.courseId)
      .map((c, i) => ({
        rank: i + 1, course_id: c.courseId, course_name: c.courseName, institution: c.institution,
      })),
    upu_status: form.upuStatus,
    field_of_study: form.fieldOfStudy,
    other_scholarships: form.otherScholarships,
    other_scholarships_text: form.otherScholarshipsText.trim(),
    help_university: form.helpUniversity,
    help_scholarship: form.helpScholarship,
    anything_else: form.anythingElse.trim(),
    declaration_name: form.declarationName.trim(),
    form_data: {},
  }
}

/** True when the form's NRIC differs from what's on the profile (needs a claim call). */
export function nricChanged(form: ApplyFormState, profile?: StudentProfile | null): boolean {
  return form.nric.trim() !== (profile?.nric ?? '').trim()
}

/**
 * Returns the i18n error sub-key for the first validation problem, or null if the
 * form is ready to submit. Ordered by tab (About Me → My Family → My Plans →
 * consent) so the earliest-section problem surfaces first. The full NRIC age/state
 * checks and the academic floor are enforced server-side (claim endpoint / profile).
 *
 * `examType` lets the Plans check be context-aware: an SPM leaver who has decided
 * must pick a pathway from the dropdown, whereas an STPM student's "decided" branch
 * is a degree picker (built in P5), so the pathway requirement is skipped for them.
 */
export function applyFormError(form: ApplyFormState, examType?: Qualification): string | null {
  // About Me — all required.
  if (!form.name.trim()) return 'name'
  if (!form.school.trim()) return 'school'
  if (!NRIC_RE.test(form.nric.trim())) return 'nric'
  if (!form.referringOrg) return 'org'
  if (!form.homeState) return 'state'
  if (!isValidPhone(form.phone)) return 'phone'
  // My Family — household size + income both required; together they drive the
  // per-capita need calc (income ÷ size), so size must be at least 1.
  const size = toIntOrNull(form.householdSize)
  if (size === null || size < 1) return 'householdSize'
  if (toIntOrNull(form.householdIncome) === null) return 'income'
  // Parent/guardian phone is optional, but if given it must be a valid number.
  if (form.parentPhone.trim() && !isValidPhone(form.parentPhone)) return 'parentPhone'
  // My Plans — the student must answer whether they've decided; "uncertain" is a
  // valid answer (it never traps an unsure student). A decided SPM leaver must then
  // pick a pathway from the eligible-only dropdown.
  if (!form.pathwayCertainty) return 'pathwayCertainty'
  if (form.pathwayCertainty === 'sure' && examType !== 'stpm' && !form.chosenPathway) return 'chosenPathway'
  // A decided programme-pathway (poly/asasi/university/kkom/pismp/iljtm/ilkbs) needs the one
  // chosen course; the institution pathways (matric/stpm) take the P4 stream/track flow instead.
  if (form.pathwayCertainty === 'sure' && examType !== 'stpm'
      && isProgrammePathway(form.chosenPathway) && !form.chosenProgramme) return 'chosenProgramme'
  // A decided institution pathway (matriculation / STPM) needs the track-or-stream and
  // then the college-or-school.
  if (form.pathwayCertainty === 'sure' && examType !== 'stpm' && isInstitutionPathway(form.chosenPathway)) {
    if (!form.preUTrack) return 'preUTrack'
    if (!form.preUInstitution) return 'preUInstitution'
  }
  // A decided STPM student picks a degree directly (no SPM pathway/track step).
  if (form.pathwayCertainty === 'sure' && examType === 'stpm' && !form.chosenProgramme) return 'chosenProgramme'
  // The Uncertain branch is intentionally non-blocking — leanings/reasons/note are optional.
  // My Support — consent + the signed declaration are both required to apply. (The
  // name-match is only a soft nudge — see declarationNameMismatch — so it never blocks.)
  if (!form.consentToContact) return 'consent'
  if (!form.declarationName.trim()) return 'declaration'
  return null
}

/** Normalise a name for forgiving comparison: trim, collapse internal whitespace, lowercase. */
function normaliseName(s: string): string {
  return s.trim().replace(/\s+/g, ' ').toLowerCase()
}

/**
 * True when a signature has been typed but doesn't loosely match the About Me name.
 * Soft signal only — it surfaces a gentle nudge, it never blocks submission. We can't
 * verify against the official IC name (we only hold what the student typed in About Me),
 * so a mismatch is worth flagging but not worth trapping a genuine student over.
 */
export function declarationNameMismatch(form: ApplyFormState): boolean {
  const signature = normaliseName(form.declarationName)
  const name = normaliseName(form.name)
  return !!signature && !!name && signature !== name
}

// ── My Results → onboarding round-trip (Sprint 9b) ───────────────────────
// Editing/adding results sends the student through the full onboarding flow.
// The apply form only commits on submit, so before leaving we STASH the
// in-progress About Me / My Family edits and set a RETURN marker; the final
// onboarding step reads the marker to route back here (and we restore the stash).
// sessionStorage keys are constants (not string literals) to avoid drift.
export const APPLY_STASH_KEY = 'halatuju_apply_stash'
export const APPLY_RETURN_KEY = 'halatuju_apply_return'

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

/** sessionStorage if available (browser), else null (SSR / node tests without injection). */
function safeSession(): StorageLike | null {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null
  } catch {
    return null
  }
}

/** Stash the in-progress form and mark that onboarding should return to the apply page. */
export function stashApplyForm(form: ApplyFormState, storage?: StorageLike): void {
  const s = storage ?? safeSession()
  if (!s) return
  s.setItem(APPLY_STASH_KEY, JSON.stringify(form))
  s.setItem(APPLY_RETURN_KEY, '1')
}

/** Read and consume the stashed form (returns null if none / unparseable). */
export function popApplyStash(storage?: StorageLike): ApplyFormState | null {
  const s = storage ?? safeSession()
  if (!s) return null
  const raw = s.getItem(APPLY_STASH_KEY)
  if (!raw) return null
  s.removeItem(APPLY_STASH_KEY)
  try {
    return JSON.parse(raw) as ApplyFormState
  } catch {
    return null
  }
}

/** Non-destructive read of the stash. Onboarding pages visited during the
 *  edit-results detour use this to prefer the in-progress apply edit over
 *  the older profile value — so shared fields (homeState) don't appear to
 *  re-prompt the student. The apply page still pops the stash on return. */
export function peekApplyStash(storage?: StorageLike): ApplyFormState | null {
  const s = storage ?? safeSession()
  if (!s) return null
  const raw = s.getItem(APPLY_STASH_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as ApplyFormState
  } catch {
    return null
  }
}

/** True when onboarding was entered from the apply form (should return to it). */
export function hasApplyReturn(storage?: StorageLike): boolean {
  const s = storage ?? safeSession()
  return !!s && s.getItem(APPLY_RETURN_KEY) === '1'
}

/** Clear the return marker (after routing back to the apply page). */
export function clearApplyReturn(storage?: StorageLike): void {
  const s = storage ?? safeSession()
  s?.removeItem(APPLY_RETURN_KEY)
}

// ── STEP 2: deeper-info + funding-need form (Sprint 4b) ──────────────────

export interface DetailsFormState {
  // Card A — About your family (S2)
  firstInFamily: boolean
  parentsOccupation: string
  // S15: how many siblings are currently studying (proxy for family education
  // burden). String for the <input> (empty = "not provided"); converts to
  // int|null in buildDetailsPayload, mirroring programmeMonths. The legacy
  // boolean is dropped from the form state; backend still accepts it for
  // back-compat from older clients.
  siblingsStudyingCount: string
  familyContext: string
  // Card B — About you (S2; aspirations/plans/fears pre-existing, daily_life new)
  aspirations: string
  plans: string
  fears: string
  dailyLife: string
  // Legacy field (kept for backward compatibility; no longer part of completeness)
  justification: string
  // "How you'd use the support" — the S3 reframe
  fundingCategories: string[]
  fundingNote: string
  programmeMonths: string  // string for the <select>; converted to int|null in buildDetailsPayload
  // Address (S14) — under "About your family" in the Story tab. Round-trips
  // through the profile (the save endpoint writes it to profile.address/etc).
  // State is sourced from /apply (profile.preferred_state) and not editable here.
  address: string
  postalCode: string
  city: string
}

export function emptyDetailsForm(): DetailsFormState {
  return {
    // Card A — About your family
    firstInFamily: false,
    parentsOccupation: '',
    siblingsStudyingCount: '',
    familyContext: '',
    // Card B — About you
    aspirations: '',
    plans: '',
    fears: '',
    dailyLife: '',
    justification: '',
    // Funding
    fundingCategories: [],
    fundingNote: '',
    programmeMonths: '',
    // Address
    address: '',
    postalCode: '',
    city: '',
  }
}

export function applicationToDetailsForm(app: ScholarshipApplication): DetailsFormState {
  const fn = app.funding_need
  return {
    // Card A — About your family (S2 narrative fields)
    firstInFamily: !!app.first_in_family,
    parentsOccupation: app.parents_occupation || '',
    // S15: prefer the count; if older data only has the boolean, surface "1" as
    // a best-effort starter so the field isn't blank for a known siblings_studying user.
    siblingsStudyingCount: app.siblings_studying_count != null
      ? String(app.siblings_studying_count)
      : (app.siblings_studying ? '1' : ''),
    familyContext: app.family_context || '',
    // Card B — About you
    aspirations: app.aspirations || '',
    plans: app.plans || '',
    fears: app.fears || '',
    dailyLife: app.daily_life || '',
    justification: app.justification || '',
    // Funding
    fundingCategories: fn?.categories ?? [],
    fundingNote: fn?.funding_note ?? '',
    programmeMonths: fn?.programme_months != null ? String(fn.programme_months) : '',
    // Address — pre-fill from the profile fields the read serializer exposes.
    address: app.address || '',
    postalCode: app.postal_code || '',
    city: app.city || '',
  }
}

export function buildDetailsPayload(f: DetailsFormState): Record<string, unknown> {
  // Convert programmeMonths string to int or null
  const pm = f.programmeMonths.trim()
  const programmeMonthsInt = pm !== '' ? (parseInt(pm, 10) || null) : null

  return {
    // Card A — About your family (snake_case for the backend)
    first_in_family: f.firstInFamily,
    parents_occupation: f.parentsOccupation.trim(),
    // S15: emit the count (int|null); the legacy boolean is no longer sent by
    // this client — the backend keeps accepting it from older clients during
    // the back-compat window (TD-061 will drop the column next session).
    siblings_studying_count: f.siblingsStudyingCount.trim() !== ''
      ? (parseInt(f.siblingsStudyingCount.trim(), 10) || 0)
      : null,
    family_context: f.familyContext.trim(),
    // Card B — About you
    aspirations: f.aspirations.trim(),
    plans: f.plans.trim(),
    fears: f.fears.trim(),
    daily_life: f.dailyLife.trim(),
    justification: f.justification.trim(),
    funding_need: {
      categories: f.fundingCategories,
      funding_note: f.fundingNote.trim(),
      programme_months: programmeMonthsInt,
    },
    // Address — backend save_application_details writes these to the profile.
    address: f.address.trim(),
    postal_code: f.postalCode.trim(),
    city: f.city.trim(),
  }
}

// ── Next-steps tabbed shell (Sprint S1) ─────────────────────────────────

/**
 * The 5 tabs shown to a shortlisted applicant on /scholarship/application.
 * Referee has been moved to the admin verify-&-accept flow and is NOT in this list.
 */
export const NEXT_STEP_ORDER = ['quiz', 'story', 'funding', 'documents', 'consent'] as const
export type NextStepKey = typeof NEXT_STEP_ORDER[number]

/**
 * Determine the initial tab: first incomplete step, falling back to 'quiz'.
 * Documents and Consent have no completeness signal yet (added in S4/S5),
 * so they are treated as always incomplete for the purpose of this default.
 */
export function defaultNextTab(
  completeness: { quiz_done: boolean; details_done: boolean; funding_done: boolean } | null | undefined,
): NextStepKey {
  if (!completeness) return 'quiz'
  if (!completeness.quiz_done) return 'quiz'
  if (!completeness.details_done) return 'story'
  if (!completeness.funding_done) return 'funding'
  return 'quiz'
}

// ── Documents (Sprint 5b / S4 redesign) ─────────────────────────────────

/** The two documents every applicant must provide. */
export const COMPULSORY_DOC_TYPES = ['ic', 'results_slip'] as const

/** Any one of these counts as proof of household income (combined card). */
export const INCOME_PROOF_TYPES = ['str', 'salary_slip', 'epf'] as const

/**
 * S17 — additional documents only relevant when the applicant is a minor:
 * - `parent_ic` is COMPULSORY for any minor (the parent/guardian's IC).
 * - `guardianship_letter` is COMPULSORY when the consenting adult is NOT the
 *   father or mother (court-issued order or parent's written authorisation).
 *
 * Both surface in the Documents tab when `isMinor` so the student can upload
 * them in advance, before reaching the Consent step. The Consent submit
 * blocks (with a backend 400) until the relevant doc(s) are present.
 */
export const MINOR_GUARDIAN_DOC_TYPES = ['parent_ic', 'guardianship_letter'] as const

/** Optional docs shown as individual cards (excluding the income group). */
export const OTHER_OPTIONAL_DOC_TYPES = [
  'water_bill', 'electricity_bill', 'statement_of_intent', 'offer_letter', 'photo',
] as const

/**
 * Full union of all doc types known to the frontend.
 * `reference_letter` is kept for back-compat (admin stage) but not shown in
 * the student UI.
 */
export const DOC_TYPES = [
  ...COMPULSORY_DOC_TYPES,
  ...INCOME_PROOF_TYPES,
  ...OTHER_OPTIONAL_DOC_TYPES,
  ...MINOR_GUARDIAN_DOC_TYPES,
  'reference_letter',
] as const
export type DocType = typeof DOC_TYPES[number]

/**
 * Returns true when an applicant has uploaded the compulsory documents.
 * S22: parent_ic is compulsory for everyone (the admin cross-checks STR/EPF
 * and similar supporting documents — usually issued in a parent's name —
 * against the parent's IC).
 * S23: proof of household income is compulsory too — any one of
 * INCOME_PROOF_TYPES satisfies it. STR recipients are nudged in the UI to
 * also upload salary/EPF for each working household member, but one upload
 * is enough to pass the completeness gate.
 * The conditional `guardianship_letter` for minors with non-parent guardians
 * is enforced separately at the consent submit step.
 */
export function documentsComplete(presentTypes: string[]): boolean {
  const present = new Set(presentTypes)
  const hasCompulsory = ['ic', 'results_slip', 'parent_ic'].every((t) => present.has(t))
  const hasIncomeProof = INCOME_PROOF_TYPES.some((t) => present.has(t))
  return hasCompulsory && hasIncomeProof
}

export function formatFileSize(bytes: number): string {
  if (!bytes || bytes < 0) return '0 KB'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
