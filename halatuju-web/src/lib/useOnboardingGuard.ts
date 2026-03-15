import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { KEY_GRADES, KEY_STPM_GRADES } from '@/lib/storage'

/**
 * Redirects to /onboarding/exam-type if the user hasn't completed onboarding
 * (no SPM or STPM grades in localStorage).
 *
 * Returns { ready } — true once the check is done and the user can stay.
 */
export function useOnboardingGuard() {
  const router = useRouter()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const hasGrades =
      localStorage.getItem(KEY_GRADES) || localStorage.getItem(KEY_STPM_GRADES)
    if (!hasGrades) {
      router.replace('/onboarding/exam-type')
    } else {
      setReady(true)
    }
  }, [router])

  return { ready }
}
