'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'

export default function AuthCallbackPage() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Supabase handles the OAuth callback automatically via the URL hash.
    // We just need to wait for the session to be available, then redirect.
    const checkSession = async () => {
      // Small delay to let Supabase process the callback
      await new Promise(resolve => setTimeout(resolve, 500))

      const { session, error } = await getSession()
      if (error) {
        setError(error.message)
        return
      }
      if (session) {
        router.replace('/dashboard')
      } else {
        setError('Authentication failed. Please try again.')
      }
    }

    checkSession()
  }, [router])

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <a href="/login" className="btn-primary">Back to Login</a>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-white">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
        <p className="text-gray-600">Completing sign in...</p>
      </div>
    </main>
  )
}
