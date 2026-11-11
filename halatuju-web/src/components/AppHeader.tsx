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
import { usePathname } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { useProfileCompleteness } from '@/lib/useProfileCompleteness'
import { signOutStudent } from '@/lib/studentSignOut'
import StudentTabBar from './StudentTabBar'
import type { Who } from './StudentMenus'

type Menus = typeof import('./StudentMenus')

/** The `lg` breakpoint, where the desktop row takes over from the phone bar. */
const DESKTOP = '(min-width: 1024px)'

export default function AppHeader({ defaultMenuOpen = false, tabs = true }: {
  /** Opens the phone menu on mount. The design sandbox's "menu open" surfaces only. */
  defaultMenuOpen?: boolean
  /**
   * The phone's bottom tab bar (`StudentTabBar`, Mobile M4b). Off for a focused flow that keeps the
   * student header (scholarship onboarding) and for the sponsor side (M5 gives sponsors their own).
   */
  tabs?: boolean
}) {
  const { t } = useT()
  const pathname = usePathname()
  const { session, isAuthenticated, isAnonymous, hasSession, showAuthGate } = useAuth()
  const { incompleteCount } = useProfileCompleteness()
  const [menuOpen, setMenuOpen] = useState(defaultMenuOpen)
  const [menus, setMenus] = useState<Menus | null>(null)
  const started = useRef(false)

  // The menus' chunk, fetched once. ⚠ IT CAN FAIL — a tab open across a deploy asks for a chunk that
  // no longer exists, and a phone fetches it on the first tap, maybe hours later. Then `failed`: the
  // menu closes again (no sheet will come, and `aria-expanded` must not say otherwise) and the bar
  // draws its small EAGER fallback — Log in signed out, Log out signed in (the same safe sign-out the
  // menus use) — on phones beside the menu button and on desktop in place of the nav row. The next
  // tap or hover tries the chunk again.
  const [failed, setFailed] = useState(false)
  const load = useCallback(() => {
    if (started.current) return
    started.current = true
    import('./StudentMenus').then((m) => { setFailed(false); setMenus(m) }).catch(() => {
      started.current = false
      setFailed(true)
      setMenuOpen(false)
    })
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

  const studentLogin = () => showAuthGate('profile')

  const meta = session?.user?.user_metadata
  const name: string = meta?.full_name || meta?.name || ''
  // TD-454: a Google sign-in still on its NRIC step (`needs-nric`) is signed in for the header — her name
  // and Log out — though not `isAuthenticated`; the account-only links stay behind `isAuthenticated`.
  const signedIn = isAuthenticated || (!!hasSession && !isAnonymous)
  const who: Who | null = signedIn ? {
    unverified: !isAuthenticated,
    name,
    contact: session?.user?.email || session?.user?.phone || '',
    initials: name ? name.split(/\s+/).filter(Boolean).map((n: string) => n[0]).join('').toUpperCase().slice(0, 2) : '?',
  } : null

  const LOG_IN = 'inline-flex min-h-11 items-center whitespace-nowrap rounded-lg border border-primary-600 px-3 text-sm font-medium text-primary-700 hover:bg-primary-50'
  const logIn = pathname?.startsWith('/sponsor') ? (
    // On the sponsor side (the signed-out sponsor landing) "Log in" is the SPONSOR's door:
    // the student gate there would greet a returning sponsor with the student sign-in.
    <Link href="/sponsor/login" className={LOG_IN}>{t('header.login.label')}</Link>
  ) : (
    <button type="button" onClick={studentLogin} className={LOG_IN}>{t('header.login.label')}</button>
  )
  // The menus' chunk failed: Log out must still be reachable (the same safe sign-out as the menus).
  const logOut = (
    <button type="button" onClick={() => { void signOutStudent() }}
      className="inline-flex min-h-11 items-center whitespace-nowrap rounded-lg px-3 text-sm font-medium text-critical-600 hover:bg-critical-50">
      {t('header.logout')}
    </button>
  )
  const fallback = failed && !menus

  return (
    <>
    <header data-app-header className="sticky top-0 z-10 border-b bg-ground-0 pt-[env(safe-area-inset-top)]">
      {/* ⚠ ONE ROW, NO WRAP. Every item but the logo is a fixed, measured width (navLayout.test.ts). */}
      <div className="container mx-auto flex items-center gap-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center">
          <BrandLogo width={120} height={40} priority />
        </Link>

        {menus ? (
          <menus.DesktopBar who={who} incompleteCount={incompleteCount} />
        ) : (
          // ⚠ `min-h-11`: the desktop row's 44 px items, reserved before they arrive, so the bar does
          // not grow 4 px under every desktop page when the chunk lands. A pointer here retries a
          // failed chunk; meanwhile the fallback keeps the way in (or out).
          <div className="hidden min-h-11 flex-1 items-center justify-end gap-2 lg:flex"
            onPointerEnter={fallback ? load : undefined}>
            {fallback && (who ? logOut : logIn)}
          </div>
        )}

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
          ) : logIn}
          {fallback && who && logOut}
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
        <menus.PhoneMenu open={menuOpen} onClose={() => setMenuOpen(false)} who={who} incompleteCount={incompleteCount} />
      )}
    </header>
    {tabs && <StudentTabBar />}
    </>
  )
}
