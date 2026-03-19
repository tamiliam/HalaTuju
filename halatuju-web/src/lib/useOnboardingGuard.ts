import { useAuth } from '@/lib/auth-context'
import { KEY_GRADES, KEY_STPM_GRADES } from '@/lib/storage'

/**
 * Guards pages that require a completed profile with grades.
 * Reads from AuthProvider state, with localStorage fallback for grades
 * (profile may not have refreshed yet after onboarding entry).
 *
 * Returns:
 * - { ready: false, loading: true, needsNric: false } — AuthProvider still resolving
 * - { ready: false, loading: false, needsNric: true } — user needs NRIC verification
 * - { ready: false, loading: false, needsNric: false } — no grades, redirect to onboarding
 * - { ready: true, loading: false, needsNric: false } — grades present, page can render
 */
export function useOnboardingGuard() {
  const { status, profile } = useAuth()

  if (status === 'loading') {
    return { ready: false, loading: true, needsNric: false }
  }

  if (status === 'needs-nric') {
    return { ready: false, loading: false, needsNric: true }
  }

  if (status === 'anonymous') {
    // Anonymous users: check localStorage for grades (onboarding without account)
    const hasLocalGrades = (() => {
      try {
        const g = localStorage.getItem(KEY_GRADES)
        if (g && Object.keys(JSON.parse(g)).length > 0) return true
        const sg = localStorage.getItem(KEY_STPM_GRADES)
        if (sg && Object.keys(JSON.parse(sg)).length > 0) return true
      } catch { /* ignore */ }
      return false
    })()
    return { ready: hasLocalGrades, loading: false, needsNric: false }
  }

  // status === 'ready' — check profile first, fall back to localStorage
  const hasGrades = profile?.grades && Object.keys(profile.grades).length > 0
  const hasStpmGrades = profile?.stpm_grades && Object.keys(profile.stpm_grades).length > 0

  if (hasGrades || hasStpmGrades) {
    return { ready: true, loading: false, needsNric: false }
  }

  // Profile may be stale (grades entered during onboarding but not yet synced/refreshed)
  const hasLocalGrades = (() => {
    try {
      const g = localStorage.getItem(KEY_GRADES)
      if (g && Object.keys(JSON.parse(g)).length > 0) return true
      const sg = localStorage.getItem(KEY_STPM_GRADES)
      if (sg && Object.keys(JSON.parse(sg)).length > 0) return true
    } catch { /* ignore */ }
    return false
  })()

  return { ready: hasLocalGrades, loading: false, needsNric: false }
}
