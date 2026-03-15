import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/lib/auth-context'
import { getProfile } from '@/lib/api'

const COMPLETENESS_FIELDS = [
  'name', 'nric', 'gender', 'preferred_state',
  'phone', 'email', 'family_income', 'siblings', 'address',
] as const

export function useProfileCompleteness() {
  const { token, isAuthenticated } = useAuth()
  const [incompleteCount, setIncompleteCount] = useState(0)
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const profile = await getProfile({ token })
      let count = 0
      for (const field of COMPLETENESS_FIELDS) {
        const val = (profile as unknown as Record<string, unknown>)[field]
        if (val === null || val === undefined || val === '') count++
      }
      setIncompleteCount(count)
      setLoaded(true)
    } catch {
      // Non-critical
    }
  }, [token])

  useEffect(() => {
    if (isAuthenticated && token) refresh()
  }, [isAuthenticated, token, refresh])

  return { incompleteCount, loaded, refresh }
}
