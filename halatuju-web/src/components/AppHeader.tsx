'use client'

import { useState, useRef, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { signOut } from '@/lib/supabase'
import { clearAll } from '@/lib/storage'
import { useT } from '@/lib/i18n'
import LanguageSelector from './LanguageSelector'

export default function AppHeader() {
  const { t } = useT()
  const pathname = usePathname()
  const { session, isAuthenticated, showAuthGate } = useAuth()
  const [profileOpen, setProfileOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  // Close profile dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSignOut = async () => {
    // Wipe all student data from localStorage before signing out
    clearAll()

    await signOut()
    window.location.href = '/'
  }

  const navLinks = [
    { href: '/dashboard', label: t('common.dashboard') },
    { href: '/search', label: t('search.nav') },
    { href: '/saved', label: t('common.saved') },
    { href: '/profile', label: t('header.myProfile'), authRequired: true as const },
  ]

  // User display info from Supabase session metadata
  const userName =
    session?.user?.user_metadata?.full_name ||
    session?.user?.user_metadata?.name ||
    ''
  const userContact = session?.user?.email || session?.user?.phone || ''
  const initials = userName
    ? userName
        .split(' ')
        .map((n: string) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '?'

  return (
    <header className="bg-white border-b sticky top-0 z-10">
      <div className="container mx-auto px-6 py-3 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center shrink-0">
          <Image src="/logo-icon.png" alt="HalaTuju" width={120} height={40} priority />
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1 ml-8">
          {navLinks.map((link) => (
            link.authRequired && !isAuthenticated ? (
              <button
                key={link.href}
                onClick={() => showAuthGate('profile')}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors text-gray-600 hover:text-gray-900 hover:bg-gray-50`}
              >
                {link.label}
              </button>
            ) : (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  pathname === link.href
                    ? 'text-primary-600 bg-primary-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {link.label}
              </Link>
            )
          ))}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Right side — desktop */}
        <div className="hidden md:flex items-center gap-3">
          <LanguageSelector />

          {isAuthenticated ? (
            <div className="relative" ref={profileRef}>
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-600 flex items-center justify-center text-sm font-semibold">
                  {initials}
                </div>
                <svg
                  className={`w-4 h-4 text-gray-400 transition-transform ${profileOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {profileOpen && (
                <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-xl shadow-lg border border-gray-200 py-2 z-20">
                  {(userName || userContact) && (
                    <div className="px-4 py-2 border-b border-gray-100">
                      {userName && (
                        <p className="text-sm font-medium text-gray-900 truncate">{userName}</p>
                      )}
                      {userContact && (
                        <p className="text-xs text-gray-500 truncate">{userContact}</p>
                      )}
                    </div>
                  )}
                  <Link
                    href="/profile"
                    className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    onClick={() => setProfileOpen(false)}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    {t('header.myProfile')}
                  </Link>
                  <Link
                    href="/outcomes"
                    className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    onClick={() => setProfileOpen(false)}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                    {t('header.myApplications')}
                  </Link>
                  <Link
                    href="/settings"
                    className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    onClick={() => setProfileOpen(false)}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {t('common.settings')}
                  </Link>
                  <div className="border-t border-gray-100 mt-1 pt-1">
                    <button
                      onClick={handleSignOut}
                      className="flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 w-full text-left"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      {t('header.logout')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <Link href="/login" className="btn-primary text-sm px-4 py-2">
              {t('common.getStarted')}
            </Link>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 rounded-lg hover:bg-gray-50"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Menu"
        >
          {mobileOpen ? (
            <svg className="w-6 h-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="w-6 h-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t bg-white">
          <div className="container mx-auto px-6 py-4 space-y-1">
            {navLinks.map((link) => (
              link.authRequired && !isAuthenticated ? (
                <button
                  key={link.href}
                  onClick={() => { setMobileOpen(false); showAuthGate('profile') }}
                  className="block w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50"
                >
                  {link.label}
                </button>
              ) : (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`block px-3 py-2.5 rounded-lg text-sm font-medium ${
                    pathname === link.href
                      ? 'text-primary-600 bg-primary-50'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                  onClick={() => setMobileOpen(false)}
                >
                  {link.label}
                </Link>
              )
            ))}

            {isAuthenticated && (
              <>
                <div className="border-t border-gray-100 pt-2 mt-2">
                  {userName && (
                    <p className="px-3 py-1 text-xs text-gray-400 font-medium">{userName}</p>
                  )}
                  <Link
                    href="/profile"
                    className="block px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
                    onClick={() => setMobileOpen(false)}
                  >
                    {t('header.myProfile')}
                  </Link>
                  <Link
                    href="/outcomes"
                    className="block px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
                    onClick={() => setMobileOpen(false)}
                  >
                    {t('header.myApplications')}
                  </Link>
                  <Link
                    href="/settings"
                    className="block px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
                    onClick={() => setMobileOpen(false)}
                  >
                    {t('common.settings')}
                  </Link>
                </div>
                <div className="border-t border-gray-100 pt-2 mt-2">
                  <button
                    onClick={handleSignOut}
                    className="block w-full text-left px-3 py-2.5 rounded-lg text-sm text-red-600 hover:bg-red-50"
                  >
                    {t('header.logout')}
                  </button>
                </div>
              </>
            )}

            {!isAuthenticated && (
              <div className="border-t border-gray-100 pt-3 mt-2">
                <Link
                  href="/login"
                  className="block btn-primary text-sm text-center"
                  onClick={() => setMobileOpen(false)}
                >
                  {t('common.getStarted')}
                </Link>
              </div>
            )}

            <div className="border-t border-gray-100 pt-3 mt-2">
              <LanguageSelector />
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
