'use client'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'

/**
 * The logged-out auth cluster: a "Log in ▾" dropdown (Student / Sponsor / Partner)
 * + a "Sign Up" button. Shared by the app header and the landing nav so the two
 * stay identical. Student → the auth-gate modal; Sponsor → /sponsor/login;
 * Partner → /admin/login; Sign Up → the /get-started chooser.
 */
export default function AuthButtons() {
  const { t } = useT()
  const router = useRouter()
  const { showAuthGate } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  return (
    <div className="flex items-center gap-2">
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1 text-sm font-medium text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-50"
        >
          {t('header.login.label')}
          <svg className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {open && (
          <div className="absolute right-0 top-full mt-1 w-52 bg-white rounded-xl shadow-lg border border-gray-200 py-2 z-20">
            <button
              onClick={() => { setOpen(false); showAuthGate('profile') }}
              className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              {t('header.login.student')}
            </button>
            <Link
              href="/sponsor/login"
              onClick={() => setOpen(false)}
              className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              {t('header.login.sponsor')}
            </Link>
            <a href="/admin/login" className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
              {t('header.login.partner')}
            </a>
          </div>
        )}
      </div>
      <button
        onClick={() => router.push('/get-started')}
        className="bg-primary-500 text-white text-sm font-medium px-4 py-1.5 rounded-lg hover:bg-primary-600 transition-colors whitespace-nowrap"
      >
        {t('header.signUp')}
      </button>
    </div>
  )
}
