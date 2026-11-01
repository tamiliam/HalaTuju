'use client'

/**
 * THE student header — one bar on every student page, Home included (Mobile M2, owner-approved
 * Stitch M2a / M2b / M2d2, 2026-11-01).
 *
 * PHONE (below `lg`): ONE row that fits a 360 px phone in Tamil and Malay — the logo (never
 * shrinks), then signed out a "Log in" button (the student sign-in gate — on the sponsor side the
 * sponsor login; partners log in from the menu), signed in her avatar (to her profile, with the "still to fill" badge), and a
 * 44 px menu button. Two buttons do not fit: "Log in" + "Sign up" measured 385 px in Tamil against
 * 358 at 390 wide (owner: Log in in the bar, Sign up first in the menu). The menu is the shared
 * `Sheet` — a bottom sheet, height-capped, its own scroll, every destination once.
 *
 * DESKTOP (`lg` up): the nav row as before (`DesktopBar`). BrightPath Bursary opens on a CLICK (it
 * used to open on `group-hover`, which reached iPads only through Safari's sticky hover —
 * decisions.md, Mobile M2). Theme and language left the bar: signed in they sit in the avatar's
 * dropdown, signed out behind the globe "Language" button.
 *
 * ⚠ WEIGHT — THIS FILE IS THE PHONE BAR AND NOTHING ELSE. Everything a phone does not show until a
 * tap, and everything only a desktop shows, lives in `StudentMenus` — one chunk, imported (not
 * `next/dynamic`, the InfoTip reason) the first time a phone menu opens or a pointer/focus reaches
 * its button, and at once on a screen `lg` or wider. Home used to draw a bar of its own that was
 * lighter than this header; with the desktop row inside the eager bar, Home's first load rose 2 kB
 * and pushed the route median over its budget. So: do not import ThemeSelector, LanguageSelector,
 * Sheet or AuthButtons here (navLayout.test.ts names this when the budget trips).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import BrandLogo from '@/components/BrandLogo'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { BURSARY_FILE_EVENT, hasBursaryFile, hasGrades } from '@/lib/storage'
import { useT } from '@/lib/i18n'
import { useProfileCompleteness } from '@/lib/useProfileCompleteness'
import type { NavGroup, NavLink, Who } from './StudentMenus'

type Menus = typeof import('./StudentMenus')

/** The `lg` breakpoint, where the desktop row takes over from the phone bar. */
const DESKTOP = '(min-width: 1024px)'

export default function AppHeader({ defaultMenuOpen = false }: {
  /** Opens the phone menu on mount. The design sandbox's "menu open" surfaces only. */
  defaultMenuOpen?: boolean
}) {
  const { t } = useT()
  const pathname = usePathname()
  const router = useRouter()
  const { session, isAuthenticated, showAuthGate } = useAuth()
  const { incompleteCount } = useProfileCompleteness()
  const [menuOpen, setMenuOpen] = useState(defaultMenuOpen)
  const [menus, setMenus] = useState<Menus | null>(null)
  const started = useRef(false)

  // "My Bursary" joins the BrightPath list only for a student with a file — a display hint the pages
  // that read her applications leave behind (`rememberBursaryFile`), read after mount so the server
  // render and the first paint agree. Never a gate: the hub's endpoint 404s a student with no file.
  const [bursary, setBursary] = useState(false)
  useEffect(() => {
    const read = () => setBursary(isAuthenticated && hasBursaryFile())
    read()
    window.addEventListener(BURSARY_FILE_EVENT, read)
    return () => window.removeEventListener(BURSARY_FILE_EVENT, read)
  }, [isAuthenticated, pathname])

  // The menus' chunk, fetched once. A failed fetch leaves the phone bar as it is (Log in still works).
  const load = useCallback(() => {
    if (started.current) return
    started.current = true
    import('./StudentMenus').then((m) => setMenus(m)).catch(() => { started.current = false })
  }, [])
  useEffect(() => { if (menuOpen) load() }, [menuOpen, load])
  // A desktop-wide screen needs the chunk at once (it draws the nav row). No `matchMedia` (a test
  // environment) counts as desktop, so every part of the header can be exercised.
  useEffect(() => {
    const mq = typeof window.matchMedia === 'function' ? window.matchMedia(DESKTOP) : null
    if (!mq || mq.matches) { load(); return }
    const on = (e: { matches: boolean }) => { if (e.matches) load() }
    if (mq.addEventListener) mq.addEventListener('change', on); else mq.addListener(on)
    return () => { if (mq.removeEventListener) mq.removeEventListener('change', on); else mq.removeListener(on) }
  }, [load])
  useEffect(() => { setMenuOpen((open) => open && defaultMenuOpen) }, [pathname, defaultMenuOpen])

  // Signed out, an account-only page opens the sign-in gate (or, with no results yet, onboarding).
  const onGate = (l: NavLink) => (hasGrades() ? showAuthGate(l.gate ?? 'profile') : router.push('/onboarding/exam-type'))
  const studentLogin = () => showAuthGate('profile')

  const b40Links: NavLink[] = [
    { href: '/scholarship', label: t('scholarship.subnav.apply') },
    ...(bursary ? [{ href: '/scholarship/bursary', label: t('scholarship.subnav.bursary') }] : []),
    { href: '/sponsor', label: t('scholarship.subnav.sponsor') },
  ]
  const mainLinks: NavLink[] = [
    { href: '/dashboard', label: t('common.dashboard') },
    { href: '/search', label: t('search.nav') },
    { href: '/saved', label: t('common.saved'), gate: isAuthenticated ? undefined : 'save' },
  ]
  const accountLinks: NavLink[] = [
    { href: '/profile', label: t('header.myProfile'), badge: incompleteCount || undefined },
    { href: '/settings', label: t('common.settings') },
  ]
  const phoneGroups: NavGroup[] = [
    { label: t('common.appName'), links: mainLinks },
    { label: t('scholarship.nav'), links: b40Links },
    ...(isAuthenticated ? [{ links: accountLinks }] : []),
  ]

  const meta = session?.user?.user_metadata
  const name: string = meta?.full_name || meta?.name || ''
  const who: Who | null = isAuthenticated ? {
    name,
    contact: session?.user?.email || session?.user?.phone || '',
    initials: name ? name.split(/\s+/).filter(Boolean).map((n: string) => n[0]).join('').toUpperCase().slice(0, 2) : '?',
  } : null

  return (
    <header className="sticky top-0 z-10 border-b bg-ground-0 pt-[env(safe-area-inset-top)]">
      {/* ⚠ ONE ROW, NO WRAP. Every item but the logo is a fixed, measured width (navLayout.test.ts). */}
      <div className="container mx-auto flex items-center gap-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center">
          <BrandLogo width={120} height={40} priority />
        </Link>

        {menus ? (
          <menus.DesktopBar pathname={pathname} mainLinks={mainLinks} b40Links={b40Links}
            accountLinks={accountLinks} who={who} incompleteCount={incompleteCount} onGate={onGate} />
        ) : <div className="hidden flex-1 lg:block" />}

        {/* Phone right side: one action, then the menu. */}
        <div className="ml-auto flex shrink-0 items-center gap-2 lg:hidden">
          {who ? (
            <Link href="/profile" aria-label={t('header.myProfile')}
              className="relative flex h-11 w-11 items-center justify-center rounded-lg hover:bg-ground-50">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-sm font-semibold text-primary-600">
                {who.initials}
              </span>
              {incompleteCount > 0 && (
                <span className="absolute right-0.5 top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-critical-fill text-[10px] font-bold text-critical-fill-ink">
                  {incompleteCount}
                </span>
              )}
            </Link>
          ) : pathname?.startsWith('/sponsor') ? (
            // On the sponsor side (the signed-out sponsor landing) "Log in" is the SPONSOR's door:
            // the student gate there would greet a returning sponsor with the student sign-in.
            <Link href="/sponsor/login"
              className="inline-flex min-h-11 items-center whitespace-nowrap rounded-lg border border-primary-600 px-3 text-sm font-medium text-primary-700 hover:bg-primary-50">
              {t('header.login.label')}
            </Link>
          ) : (
            <button type="button" onClick={studentLogin}
              className="inline-flex min-h-11 items-center whitespace-nowrap rounded-lg border border-primary-600 px-3 text-sm font-medium text-primary-700 hover:bg-primary-50">
              {t('header.login.label')}
            </button>
          )}
          <button type="button" aria-label={t('common.menu')} aria-expanded={menuOpen} aria-haspopup="dialog"
            onClick={() => setMenuOpen(true)} onPointerEnter={load} onFocus={load}
            className="flex h-11 w-11 items-center justify-center rounded-lg text-ground-600 hover:bg-ground-50">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </div>

      {menus && (
        <menus.PhoneMenu open={menuOpen} onClose={() => setMenuOpen(false)} pathname={pathname}
          groups={phoneGroups} who={who} onGate={onGate} onStudentLogin={studentLogin} />
      )}
    </header>
  )
}
