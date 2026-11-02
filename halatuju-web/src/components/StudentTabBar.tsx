'use client'

/**
 * THE STUDENT TAB BAR — a fixed bar of four tabs at the foot of every student page on a phone
 * (Mobile M4b, owner-approved 2026-11-02 after comparing HalaTuju with the Grab app):
 * Dashboard · Explore · Saved · BrightPath. Her profile stays the header's avatar and the header's
 * menu keeps every destination (it is the way around wherever this bar gives way).
 *
 * Mounted ONLY by `AppHeader` (a page opts out with `<AppHeader tabs={false} />`), so the pages that
 * draw no student header — onboarding, the quizzes, the sponsor portal, the console — never show it.
 *
 * ⚠ EVERYTHING ELSE IS CSS, in `globals.css` ("THE STUDENT TAB BAR"): the bar shows only below `md`,
 * gives way to a page's OWN bottom bar (any element marked `data-page-bar` — the course Save bar, the
 * saved compare bar, the apply Back / Continue bar, the award's sign bar, the post-award step tabs:
 * ONE bottom bar at a time, the page's main action wins), hides while she types, pads the page so
 * nothing ends under it and lifts the toast above it (`--bottom-bar`). A browser without `:has()`
 * (Safari < 15.4, Chrome < 105) never shows it at all — the header menu still works, and a fixed bar
 * can never cover a Save button.
 *
 * ⚠ WEIGHT: this file rides EAGERLY on every student route (it IS the navigation — the M2 lesson: a
 * lazy way around needs an eager fallback, so the way around is simply eager). No string of its own:
 * three existing core keys and the organisation's own short name ("BrightPath"), which reads the same
 * in every language. Four short icon paths.
 */
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { useBranding } from '@/lib/branding-context'
import { BURSARY_FILE_EVENT, hasBursaryFile, hasGrades } from '@/lib/storage'

/** Home, compass, bookmark, mortar board — 24 px outline icons. */
const ICON = [
  'M3 10.5 12 3l9 7.5V20a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z',
  'M12 21a9 9 0 100-18 9 9 0 000 18zm3.5-12.5-2 5-5 2 2-5z',
  'M6.5 3.5h11v17l-5.5-4-5.5 4z',
  'M2 9.5 12 5l10 4.5L12 14zm4 1.8V16c3 2.6 9 2.6 12 0v-4.7',
]

export default function StudentTabBar() {
  const { t } = useT()
  const path = usePathname() || ''
  const router = useRouter()
  const { isAuthenticated, showAuthGate } = useAuth()
  const { orgShortName } = useBranding()
  // "My Bursary" only for a student with a file — the display hint the header menu reads too
  // (`rememberBursaryFile`); never a gate (the hub's endpoint 404s anyone without a file).
  const [file, setFile] = useState(false)
  useEffect(() => {
    const read = () => setFile(isAuthenticated && hasBursaryFile())
    read()
    // The dashboard's banner writes the hint while she is ON the page: re-read at once (S3 review L5).
    window.addEventListener(BURSARY_FILE_EVENT, read)
    return () => window.removeEventListener(BURSARY_FILE_EVENT, read)
  }, [isAuthenticated, path])
  const tabs: [string, string, boolean][] = [
    ['/dashboard', t('common.dashboard'), path === '/dashboard'],
    ['/search', t('search.nav'), path === '/search'],
    ['/saved', t('common.saved'), path === '/saved'],
    [file ? '/scholarship/bursary' : '/scholarship', orgShortName, path.startsWith('/scholarship')],
  ]
  // ⚠ No classes here: the bar's look is CSS ("THE STUDENT TAB BAR" in globals.css), which costs no
  // JavaScript on any route; `aria-current` is both the screen reader's "current page" and the style.
  return (
    <nav data-tab-bar aria-label={t('common.menu')}>
      {tabs.map(([href, label, here], i) => (
        // `prefetch={false}`: four links on every page would otherwise fetch four routes' code on each
        // view in production (the phone's data); a tap loads the one she chose (M4b review).
        <Link key={i} href={href} prefetch={false} aria-current={here ? 'page' : undefined}
          // Saved needs an account: signed out it opens the sign-in sheet — or, with no results yet,
          // onboarding — exactly as the header menu's Saved does.
          onClick={i === 2 && !isAuthenticated ? (e) => {
            e.preventDefault()
            if (hasGrades()) showAuthGate('save'); else router.push('/onboarding/exam-type')
          } : undefined}>
          <svg viewBox="0 0 24 24" aria-hidden><path d={ICON[i]} /></svg>
          {label}
        </Link>
      ))}
    </nav>
  )
}
