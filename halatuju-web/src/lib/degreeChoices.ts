/**
 * THE DEGREES A TERTIARY STUDENT CAN NAME — one loader for the two degree pickers (`/scholarship/apply`
 * My Plans and `/profile`'s `PathwayPicker`). Third results route S2b, 2026-10-26.
 *
 * - **STPM**: the degrees their results qualify them for (`/stpm/eligibility/check/`) — unchanged.
 * - **Matriculation / Asasi / Diploma** (ruling D2): EVERY degree programme, UNFILTERED
 *   (`/stpm/search/`). HalaTuju holds no entry rules for these qualifications, and a CGPA cannot be
 *   matched honestly against STPM requirements — so the picker filters nothing, and the student
 *   names the degree they hold an offer for. Without this they could not apply at all. The offer
 *   letter check still governs the pathway fact (roadmap risk list).
 */
import { checkStpmEligibility, searchStpmCourses, type EligibleCourse, type StudentProfile } from '@/lib/api'
import { isThirdRoute, type Qualification } from '@/lib/qualification'
import { stpmDegreesToCourses } from '@/lib/scholarship'

export async function loadDegreeChoices(
  examType: Qualification, profile: StudentProfile, token: string,
): Promise<EligibleCourse[]> {
  if (isThirdRoute(examType)) {
    const res = await searchStpmCourses({}, { token })
    return stpmDegreesToCourses(res.courses)
  }
  const res = await checkStpmEligibility({
    stpm_grades: profile.stpm_grades || {},
    spm_grades: profile.grades || {},
    cgpa: profile.stpm_cgpa ?? 0,
    muet_band: profile.muet_band ?? 0,
    gender: profile.gender,
    nationality: profile.nationality,
    colorblind: profile.colorblind,
  }, { token })
  return stpmDegreesToCourses(res.eligible_courses)
}
