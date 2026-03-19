import { useAuth } from '@/lib/auth-context'

/**
 * Guards pages that require a completed profile with grades.
 * Reads from AuthProvider state — never from localStorage.
 *
 * Returns:
 * - { ready: false, loading: true } — AuthProvider still resolving
 * - { ready: false, loading: false } — no grades, caller should redirect
 * - { ready: true, loading: false } — grades present, page can render
 */
export function useOnboardingGuard() {
  const { status, profile } = useAuth()

  if (status === 'loading') {
    return { ready: false, loading: true }
  }

  if (status !== 'ready') {
    return { ready: false, loading: false }
  }

  const hasGrades = profile?.grades && Object.keys(profile.grades).length > 0
  const hasStpmGrades = profile?.stpm_grades && Object.keys(profile.stpm_grades).length > 0

  return { ready: !!(hasGrades || hasStpmGrades), loading: false }
}
