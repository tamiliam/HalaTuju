'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminSupabase } from '@/lib/admin-supabase'

export default function AdminAuthCallbackPage() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const supabase = getAdminSupabase()

    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        setError('Authentication failed. Please try again.')
        return
      }

      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/admin/role/`,
          {
            headers: {
              Authorization: `Bearer ${session.access_token}`,
              'Content-Type': 'application/json',
            },
          }
        )
        const role = await res.json()
        if (!role.is_admin) {
          await supabase.auth.signOut()
          setError('This account does not have admin access.')
          return
        }
      } catch {
        setError('Failed to verify admin access.')
        return
      }

      router.replace('/admin')
    })
  }, [router])

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <a href="/admin/login" className="text-blue-600 hover:underline">
            Back to login
          </a>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-gray-600">Signing in...</p>
    </main>
  )
}
