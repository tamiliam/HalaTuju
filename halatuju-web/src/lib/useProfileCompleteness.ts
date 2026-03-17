import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/lib/auth-context'
import { getProfile } from '@/lib/api'

const COMPLETENESS_FIELDS = [
  'name', 'nric', 'gender', 'preferred_state',
  'phone', 'email', 'family_income', 'siblings', 'address',
  'angka_giliran',
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

  // Re-fetch when profile is saved from another component
  useEffect(() => {
    const handler = () => { refresh() }
    window.addEventListener('profile-updated', handler)
    return () => window.removeEventListener('profile-updated', handler)
  }, [refresh])

  return { incompleteCount, loaded, refresh }
}
