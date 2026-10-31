/**
 * "ELIGIBLE ONLY" — THE ONE PLACE THE SCHOLARSHIP PICKER ASKS ABOUT RESULTS (Scholarship My Plans
 * redesign, owner rulings 2026-10-30). Loaded with `import()` only when the student switches
 * "Eligible only" ON; off — the default — the picker lists the whole catalogue (`lib/planPicker.ts`).
 * `lib/planPicker.scope.test.ts` holds that this is the only picker module that may call the
 * eligibility endpoints, and that the picker reaches it only through `import()`.
 *
 * - SPM results: the courses `/eligibility/check/` returns, the pathways with any (its
 *   `pathway_stats`), and the matriculation tracks `/calculate/pathways/` flags eligible.
 * - STPM results: the degrees `/stpm/eligibility/check/` returns.
 * - Matriculation / Asasi / Diploma (the third route): HalaTuju holds no entry rules for them
 *   (ruling D2), so the switch is not offered and this is never called for them.
 *
 * ⚠ OPTION A STILL HOLDS (decisions.md 2026-10-28): each check is sent `bumiputera: true`, so a
 * Bumiputera-only course is never hidden by the student's answer — that answer is course-guide
 * only and is not read here.
 */
import {
  calculatePathways, checkEligibility, checkStpmEligibility, getPathwayOfferings, type StudentProfile,
} from '@/lib/api'
import type { Qualification } from '@/lib/qualification'
import { PATHWAY_ORDER } from '@/lib/scholarship'

export interface PlanEligibility {
  courseIds: ReadonlySet<string>
  pathways: ReadonlySet<string>
  matricTracks: string[]
}

export async function loadPlanEligibility(
  examType: Qualification, profile: StudentProfile, token: string,
): Promise<PlanEligibility> {
  if (examType === 'stpm') {
    const res = await checkStpmEligibility({
      stpm_grades: profile.stpm_grades || {},
      spm_grades: profile.grades || {},
      cgpa: profile.stpm_cgpa ?? 0,
      muet_band: profile.muet_band ?? 0,
      gender: profile.gender,
      nationality: profile.nationality,
      colorblind: profile.colorblind,
      bumiputera: true,   // Option A: include Bumi-only degrees whatever the answer
    }, { token })
    return { courseIds: new Set(res.eligible_courses.map((d) => d.course_id)), pathways: new Set(), matricTracks: [] }
  }
  const [elig, paths] = await Promise.all([
    checkEligibility({ ...profile, bumiputera: true }, { token }),   // Option A, as above
    calculatePathways(profile.grades || {}, profile.coq_score ?? 0, null, { token }),
  ])
  const stats = elig.pathway_stats || {}
  const courseIds = new Set((elig.eligible_courses || []).map((c) => c.course_id))
  const pathways = new Set(PATHWAY_ORDER.filter((k) => (stats[k] || 0) > 0))
  // MARA's own diplomas are counted under `university` by eligibility, but the picker lists them
  // under `mara` (owner, 2026-10-31). So both are decided by the LISTS: University when its own list
  // (the division left out) holds a course she qualifies for, MARA when the division or a MARA campus
  // does. A list that fails to load leaves the count's answer standing.
  const listHasOne = async (p: string) =>
    (await getPathwayOfferings(p).catch(() => null))?.courses.some((c) => courseIds.has(c.course_id))
  if (pathways.has('university') && (await listHasOne('university')) === false) pathways.delete('university')
  if (!pathways.has('mara') && (await listHasOne('mara'))) pathways.add('mara')
  return {
    courseIds,
    pathways,
    matricTracks: (paths.pathways || []).filter((p) => p.pathway === 'matric' && p.eligible).map((p) => p.trackId),
  }
}
