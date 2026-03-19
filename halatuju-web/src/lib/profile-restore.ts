import { getProfile } from '@/lib/api'
import { KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS } from '@/lib/storage'

/**
 * Fetches the student's profile from the API and writes grades,
 * demographics, and quiz signals into localStorage as a cache.
 *
 * Returns the profile object, or null on failure.
 *
 * TECH DEBT: Routing logic currently depends on localStorage to decide
 * where to send the user (e.g. has grades → dashboard). This function
 * exists to ensure the cache is populated before those checks run.
 * The proper fix is to make routing depend on AuthProvider state, not
 * localStorage. See docs/tech-debt.md TD-003.
 */
export async function restoreProfileToLocalStorage(token: string) {
  try {
    const profile = await getProfile({ token })
    if (profile.grades && Object.keys(profile.grades).length > 0) {
      localStorage.setItem(KEY_GRADES, JSON.stringify(profile.grades))
    }
    const demo: Record<string, unknown> = {}
    if (profile.gender) demo.gender = profile.gender
    if (profile.nationality) demo.nationality = profile.nationality
    if (profile.colorblind != null) demo.colorblind = profile.colorblind
    if (profile.disability != null) demo.disability = profile.disability
    if (Object.keys(demo).length > 0) {
      localStorage.setItem(KEY_PROFILE, JSON.stringify(demo))
    }
    if (profile.student_signals) {
      localStorage.setItem(KEY_QUIZ_SIGNALS, JSON.stringify(profile.student_signals))
    }
    return profile
  } catch {
    return null
  }
}
