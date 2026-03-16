'use client'

import { AdminAuthProvider, useAdminAuth } from '@/lib/admin-auth-context'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect } from 'react'
import Link from 'next/link'
import { adminSignOut } from '@/lib/admin-supabase'

function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const { isAdminAuthenticated, isLoading, role } = useAdminAuth()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    // Don't redirect if on login or callback pages
    if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) return
    if (!isLoading && !isAdminAuthenticated) {
      router.replace('/admin/login')
    }
  }, [isAdminAuthenticated, isLoading, router, pathname])

  // Login and callback pages render without nav
  if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) {
    return <>{children}</>
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        Loading...
      </div>
    )
  }

  if (!isAdminAuthenticated) {
    return null
  }

  const handleSignOut = async () => {
    await adminSignOut()
    router.replace('/admin/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="font-bold text-blue-600">HalaTuju Admin</span>
          <Link
            href="/admin"
            className="text-sm text-gray-600 hover:text-blue-600"
          >
            Dashboard
          </Link>
          <Link
            href="/admin/students"
            className="text-sm text-gray-600 hover:text-blue-600"
          >
            Pelajar
          </Link>
          {role?.is_super_admin && (
            <Link
              href="/admin/invite"
              className="text-sm text-gray-600 hover:text-blue-600"
            >
              Invite
            </Link>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">
            {role?.admin_name}
            {role?.org_name ? ` (${role.org_name})` : ' (Super Admin)'}
          </span>
          <button
            onClick={handleSignOut}
            className="text-sm text-red-600 hover:text-red-800"
          >
            Log Out
          </button>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto p-4 md:p-6">{children}</main>
    </div>
  )
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AdminAuthProvider>
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </AdminAuthProvider>
  )
}
