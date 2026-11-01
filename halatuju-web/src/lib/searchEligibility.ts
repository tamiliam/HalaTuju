/**
 * The courses this browser's student qualifies for — her SPM results and, for an STPM student, her
 * STPM ones — as the course search's "eligible only" switch needs them (a set of ids, and each
 * course's merit for the cards). Read from this device's saved results, asked of the API.
 *
 * Moved verbatim out of `app/search/page.tsx` (Mobile M3: the page passed 600 lines when its phone
 * filter bar came). It throws on any failure; the page catches it and leaves the switch off.
 */
import { checkEligibility, checkStpmEligibility, type EligibleCourse, type StudentProfile } from '@/lib/api'
import { isBumiputera } from '@/lib/bumiputera'
import {
  KEY_PROFILE, KEY_GRADES, KEY_ALIRAN, KEY_EXAM_TYPE, KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_MUET_BAND, KEY_SPM_PREREQ,
} from '@/lib/storage'

export async function loadEligibleCourses(): Promise<{ ids: Set<string>; map: Map<string, EligibleCourse> }> {
  const allIds = new Set<string>()
  const allMap = new Map<string, EligibleCourse>()

  // SPM eligibility — merge grades (stored separately) into profile
  const stored = localStorage.getItem(KEY_PROFILE)
  const gradesStr = localStorage.getItem(KEY_GRADES)
  if (stored && gradesStr) {
    const parsedProfile = JSON.parse(stored)
    const parsedGrades = JSON.parse(gradesStr)
    // TD-063: include the explicit stream picks for the merit weighting.
    const aliranStr = localStorage.getItem(KEY_ALIRAN)
    const streamSubjects = aliranStr ? JSON.parse(aliranStr) : undefined
    const profile: StudentProfile = {
      ...parsedProfile, grades: parsedGrades,
      ...(streamSubjects && streamSubjects.length && { stream_subjects: streamSubjects }),
    }
    if (Object.keys(profile.grades).length > 0) {
      const data = await checkEligibility(profile)
      for (const c of data.eligible_courses) {
        allIds.add(c.course_id)
        allMap.set(c.course_id, c)
      }
    }
  }

  // STPM eligibility — check if STPM grades exist
  const examType = localStorage.getItem(KEY_EXAM_TYPE)
  const stpmGradesStr = localStorage.getItem(KEY_STPM_GRADES)
  const stpmCgpaStr = localStorage.getItem(KEY_STPM_CGPA)
  const muetBandStr = localStorage.getItem(KEY_MUET_BAND)
  const spmPrereqStr = localStorage.getItem(KEY_SPM_PREREQ)

  if (examType === 'stpm' && stpmGradesStr && stpmCgpaStr && muetBandStr) {
    const profileData = stored ? JSON.parse(stored) : {}
    const genderMap: Record<string, string> = { male: 'Lelaki', female: 'Perempuan' }
    const nationalityMap: Record<string, string> = { malaysian: 'Warganegara', non_malaysian: 'Bukan Warganegara' }

    const stpmData = await checkStpmEligibility({
      stpm_grades: JSON.parse(stpmGradesStr),
      spm_grades: spmPrereqStr ? JSON.parse(spmPrereqStr) : {},
      cgpa: parseFloat(stpmCgpaStr),
      muet_band: parseInt(muetBandStr),
      gender: genderMap[profileData.gender] || '',
      nationality: nationalityMap[profileData.nationality] || 'Warganegara',
      colorblind: !!profileData.colorblind,
      bumiputera: isBumiputera(profileData),   // Bumi coverage Sprint B
    })

    // Map STPM eligible courses to EligibleCourse format
    for (const prog of stpmData.eligible_courses) {
      allIds.add(prog.course_id)
      allMap.set(prog.course_id, {
        course_id: prog.course_id,
        course_name: prog.course_name,
        level: 'Ijazah Sarjana Muda',
        field: '',
        field_key: prog.field_key || '',
        source_type: 'ua',
        merit_cutoff: prog.merit_score,
        student_merit: null,
        merit_label: null,
        merit_color: null,
      })
    }
  }

  return { ids: allIds, map: allMap }
}
