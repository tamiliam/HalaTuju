/**
 * THE SCHOLARSHIP "MY PLANS" PICKER'S RULES — pure, one home (Scholarship My Plans redesign,
 * owner rulings 2026-10-30). Read by `components/PathwayPicker.tsx` (the one picker, on
 * `/scholarship/apply` and `/profile`) and `components/scholarship/InstitutionCoursePicker.tsx`.
 *
 * ⚠ THE SCHOLARSHIP SIDE DOES NOT FILTER BY RESULTS BY DEFAULT. Its pickers exist so a student
 * NAMES the course and the institution she holds (or awaits) an offer for. Entry rules change from
 * year to year, and a student already enrolled may have entered under rules her saved grades no
 * longer meet (UE4545004, a UiTM Diploma Sains student, could not pick her own course). So every
 * list here is the whole catalogue (`getPathwayOfferings`), and `allowed` is `null` — no narrowing
 * — unless she switches "Eligible only" on, which loads `lib/planEligibility.ts` on demand. The
 * course guide (dashboard, search, course pages) is a different part of the product and stays
 * filtered by results. `lib/planPicker.scope.test.ts` guards the split.
 *
 * Institution FIRST, then course, so the box she types into never holds too much:
 *   university / Asasi / an STPM degree        University → Course
 *   polytechnic, community college, MARA,
 *   ILJTM, ILKBS, other public skills training  State → Campus → Course
 *   PISMP                                      School type → Subject
 *   matriculation / Form 6                     Track or stream → College or school
 */
import type { OfferingCourse, OfferingInstitution, PathwayOfferings } from '@/lib/api'
import {
  PISMP_ALIRAN_ORDER, type ApplyFormState, type ChosenProgramme, type PismpAliran,
} from '@/lib/scholarship'

/** The STPM degree catalogue, asked for by STPM and third-route holders (University → Degree). */
export const DEGREE_PATHWAY = 'degree'

/** Programme pathways whose campuses are many: a State step comes first. The university pathways
 *  (29 universities at most) do not want one (owner, 2026-10-30). */
const STATE_FIRST = ['poly', 'kkom', 'mara', 'iljtm', 'ilkbs', 'tvet_other']
/** Pathways the offerings endpoint serves (matric / stpm use fixed college and school lists). */
const OFFERING_PATHWAYS = ['asasi', 'university', ...STATE_FIRST, 'pismp', DEGREE_PATHWAY]

/** The four matriculation tracks with a college list, in the engine's order. The two Bumi-only
 *  tracks have no college data and stay out (decisions.md 2026-10-29). */
export const MATRIC_TRACKS = ['sains', 'kejuruteraan', 'sains_komputer', 'perakaunan'] as const

export const isOfferingPathway = (key: string) => OFFERING_PATHWAYS.includes(key)
export const asksStateFirst = (key: string) => STATE_FIRST.includes(key)

/** Which institution label a pathway uses: a university, a polytechnic, a campus, or the neutral
 *  "institution". Asasi and the university pathway list polytechnics and MARA's education division
 *  too, so they ask "Which institution?"; STPM degrees are all at universities (owner, 2026-10-31). */
export function institutionKind(pathway: string): 'university' | 'institution' | 'poly' | 'campus' {
  if (pathway === 'poly') return 'poly'
  if (pathway === 'asasi' || pathway === 'university') return 'institution'
  return asksStateFirst(pathway) ? 'campus' : 'university'
}

/** `null` = no narrowing (the default); a set = the course ids "Eligible only" keeps. */
export type Allowed = ReadonlySet<string> | null

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name)
const byCourse = (a: OfferingCourse, b: OfferingCourse) => a.course_name.localeCompare(b.course_name)
const offersAny = (i: OfferingInstitution, allowed: Allowed) =>
  !allowed || i.course_ids.some((id) => allowed.has(id))

/** The states that hold at least one campus of the pathway (with an allowed course). */
export function offeringStates(o: PathwayOfferings | null, allowed: Allowed): string[] {
  if (!o) return []
  const states = new Set(o.institutions.filter((i) => i.state && !i.no_campus && offersAny(i, allowed))
    .map((i) => i.state))
  return Array.from(states).sort((a, b) => a.localeCompare(b))
}

/** The institutions to choose from — the campuses in `state` when one is given — A–Z. */
export function offeringInstitutions(
  o: PathwayOfferings | null, state: string | null, allowed: Allowed,
): OfferingInstitution[] {
  if (!o) return []
  return o.institutions
    .filter((i) => (state === null || (i.state === state && !i.no_campus)) && offersAny(i, allowed))
    .sort(byName)
}

/** Institutions with no single campus (MARA's education division under `mara`, owner 2026-10-31):
 *  offered BEFORE the state step, since no state would find them. With an allowed course only. */
export function noCampusInstitutions(o: PathwayOfferings | null, allowed: Allowed): OfferingInstitution[] {
  return o ? o.institutions.filter((i) => i.no_campus && offersAny(i, allowed)) : []
}

/** The courses one institution offers, A–Z. */
export function coursesAt(o: PathwayOfferings | null, instId: string, allowed: Allowed): OfferingCourse[] {
  const inst = o?.institutions.find((i) => i.id === instId)
  if (!o || !inst) return []
  const ids = new Set(inst.course_ids.filter((id) => !allowed || allowed.has(id)))
  return o.courses.filter((c) => ids.has(c.course_id)).sort(byCourse)
}

/** The institution an already-chosen programme names — by id, else by its catalogue name. */
export function institutionOf(o: PathwayOfferings | null, cp: ChosenProgramme | null): OfferingInstitution | undefined {
  if (!o || !cp) return undefined
  return o.institutions.find((i) => !!cp.institutionId && i.institution_id === cp.institutionId)
    ?? o.institutions.find((i) => !!cp.institution && i.name === cp.institution)
}

/** PISMP: the school types present (among allowed courses), in display order. */
export function pismpAliransOf(o: PathwayOfferings | null, allowed: Allowed): PismpAliran[] {
  if (!o) return []
  const present = new Set(o.courses.filter((c) => c.aliran && (!allowed || allowed.has(c.course_id)))
    .map((c) => c.aliran as string))
  return PISMP_ALIRAN_ORDER.filter((a) => present.has(a))
}

/** PISMP: the subjects of one school type, A–Z, one row per name (zone variants share a name). */
export function pismpBidang(o: PathwayOfferings | null, aliran: string, allowed: Allowed): OfferingCourse[] {
  if (!o || !aliran) return []
  const seen = new Set<string>()
  return o.courses
    .filter((c) => c.aliran === aliran && (!allowed || allowed.has(c.course_id)))
    .sort(byCourse)
    .filter((c) => (seen.has(c.course_name) ? false : (seen.add(c.course_name), true)))
}

/** PISMP: the school type of an already-chosen course ('' if it is not one). */
export function aliranOfCourse(o: PathwayOfferings | null, courseId: string | null | undefined): string {
  return (courseId && o?.courses.find((c) => c.course_id === courseId)?.aliran) || ''
}

/** Every degree with its university on the line under it — the waiting branch's top-3 slots. */
export function degreeChoices(o: PathwayOfferings | null, allowed: Allowed) {
  if (!o) return []
  const uni = new Map<string, string>()
  o.institutions.forEach((i) => i.course_ids.forEach((id) => uni.set(id, i.name)))
  return o.courses.filter((c) => !allowed || allowed.has(c.course_id)).sort(byCourse)
    .map((c) => ({ ...c, institution_name: uni.get(c.course_id) ?? '' }))
}

/** The programme she picked, with the institution she named (when the pathway has one). */
export function pickProgramme(c: OfferingCourse, inst?: OfferingInstitution | null): ChosenProgramme {
  const cp: ChosenProgramme = { courseId: c.course_id, courseName: c.course_name, fieldKey: c.field_key || '' }
  if (inst) { cp.institution = inst.name; cp.institutionId = inst.institution_id }
  return cp
}

/**
 * The apply form's two DERIVED answers follow a patch from the picker: every pathway is a public
 * institution, so naming one implies `upu_status = 'public_other'` (none → ''); and the chosen
 * course's field is the field of study (no separate question).
 */
export function applyPlanPatch(form: ApplyFormState, patch: Partial<ApplyFormState>): ApplyFormState {
  const next = { ...form, ...patch }
  if ('chosenPathway' in patch) next.upuStatus = patch.chosenPathway ? 'public_other' : ''
  if ('chosenProgramme' in patch) next.fieldOfStudy = patch.chosenProgramme?.fieldKey ?? ''
  return next
}
