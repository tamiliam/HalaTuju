'use client'

/**
 * The student header's MENUS — everything the header shows only after a tap (Mobile M2).
 *
 * ⚠ THIS MODULE IS ITS OWN CHUNK, imported by `AppHeader` the first time a phone menu opens (or a
 * pointer/focus reaches its button, so the first opening is usually instant), and at once on a screen
 * `lg` or wider, which draws the desktop row from here. AppHeader is on nearly every student route,
 * and `/scholarship/application` sat a fraction of a kilobyte under its first-load line: the phone
 * menu, the desktop row and its dropdowns, the theme and language pickers, Log in ▾ / Sign Up and the
 * sign-out routine all live here so that none of them rides in any route's first load. The import is
 * owned by AppHeader (not `next/dynamic`, which re-throws a failed load as a page error — the
 * InfoTip / LazyPostAwardTask lesson).
 *
 *   - `PhoneMenu`    — below `lg`, the whole menu in the shared `Sheet` (rule 5): one list, every
 *                      destination once, 48 px rows, its own scroll, Log out pinned in the footer.
 *   - `DesktopBar`   — from `lg`, the nav row; BrightPath ▾ opens on a click.
 *   - `AccountPanel` — from `lg`, the avatar's dropdown: profile, settings, theme, language, log out.
 *   - `DisplayPanel` — from `lg` and signed out, the theme + language dropdown.
 *
 * The rows are built once, by `useStudentNav` below, for both the desktop row and the phone list,
 * so the two can never disagree about what exists.
 */
import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import Sheet from '@/components/Sheet'
import AuthButtons from '@/components/AuthButtons'
import { signOutStudent } from '@/lib/studentSignOut'
import { useAuth } from '@/lib/auth-context'
import { BURSARY_FILE_EVENT, hasBursaryFile, hasGrades } from '@/lib/storage'
import { useT } from '@/lib/i18n'
// Theme + language as 44 px segments — their own module since Mobile M5 (the sponsor's My Account
// draws them too); this lazy chunk still carries them for every student menu.
import { DisplayControls } from '@/components/DisplaySegments'

/** One destination. `gate` = needs an account: a signed-out tap opens the sign-in gate instead. */
export interface NavLink {
  href: string
  label: string
  gate?: 'save' | 'profile'
  /** The profile's "fields still to fill" count, shown as a badge. */
  badge?: number
}

export interface NavGroup {
  /** A small heading over the group; none for a plain divider. */
  label?: string
  links: NavLink[]
}

export interface Who {
  /** Signed in but her NRIC step is unfinished: name and Log out only, no account-only links (TD-454). */
  unverified?: boolean
  name: string
  contact: string
  initials: string
}

const ROW = 'flex min-h-12 w-full items-center gap-3 rounded-lg px-3 text-left text-sm font-medium'
const ROW_IDLE = 'text-ground-700 hover:bg-ground-50'
const ROW_HERE = 'bg-primary-50 text-primary-700'

function Badge({ n }: { n: number }) {
  return (
    <span className="ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-critical-fill px-1.5 text-xs font-bold text-critical-fill-ink">
      {n}
    </span>
  )
}

/** One row: a link, or — for a signed-out visitor and an account-only page — a button to the gate. */
function Row({ link, here, onGo, onGate, first }: {
  link: NavLink; here: boolean; onGo: () => void; onGate: (l: NavLink) => void
  first?: RefObject<(HTMLAnchorElement & HTMLButtonElement) | null>
}) {
  const badge = link.badge ? <Badge n={link.badge} /> : null
  if (link.gate) {
    return (
      <button ref={first} type="button" onClick={() => onGate(link)} className={`${ROW} ${ROW_IDLE}`}>
        <span className="min-w-0 break-words">{link.label}</span>{badge}
      </button>
    )
  }
  return (
    <Link ref={first} href={link.href} onClick={onGo} aria-current={here ? 'page' : undefined}
      className={`${ROW} ${here ? ROW_HERE : ROW_IDLE}`}>
      <span className="min-w-0 break-words">{link.label}</span>{badge}
    </Link>
  )
}

function GroupLabel({ children }: { children: ReactNode }) {
  return <p className="px-3 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-ground-500">{children}</p>
}

/**
 * What the student header offers, built HERE rather than in AppHeader (Mobile M2 review): the lists,
 * the "My Bursary" hint and the gate for account-only pages ride in this lazy chunk, not in the eager
 * bar every student route downloads — that room paid for the bar's chunk-failure fallback.
 *
 * "My Bursary" joins the BrightPath list only for a student with a file — a display hint the pages
 * that read her applications leave behind (`rememberBursaryFile`), re-read on every navigation and
 * the moment a page writes it. Never a gate: the hub's endpoint 404s a student with no file.
 */
function useStudentNav(incompleteCount: number) {
  const { t } = useT()
  const pathname = usePathname()
  const router = useRouter()
  const { isAuthenticated, showAuthGate } = useAuth()
  const [bursary, setBursary] = useState(false)
  useEffect(() => {
    const read = () => setBursary(isAuthenticated && hasBursaryFile())
    read()
    window.addEventListener(BURSARY_FILE_EVENT, read)
    return () => window.removeEventListener(BURSARY_FILE_EVENT, read)
  }, [isAuthenticated, pathname])
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
  // Signed out, an account-only page opens the sign-in gate (or, with no results yet, onboarding).
  const onGate = (l: NavLink) => (hasGrades() ? showAuthGate(l.gate ?? 'profile') : router.push('/onboarding/exam-type'))
  return { pathname, b40Links, mainLinks, accountLinks, onGate, studentLogin: () => showAuthGate('profile') }
}

export interface PhoneMenuProps {
  open: boolean
  onClose: () => void
  /** Signed in: who she is (heads the sheet). Signed out: null. */
  who: Who | null
  incompleteCount: number
}

export function PhoneMenu({ open, onClose, who, incompleteCount }: PhoneMenuProps) {
  const { t } = useT()
  const { pathname, b40Links, mainLinks, accountLinks, onGate, studentLogin: onStudentLogin } = useStudentNav(incompleteCount)
  const groups: NavGroup[] = [
    { label: t('common.appName'), links: mainLinks },
    { label: t('scholarship.nav'), links: b40Links },
    ...(who && !who.unverified ? [{ links: accountLinks }] : []),
  ]
  const router = useRouter()
  // Focus opens on the FIRST ITEM — Sign up, or Dashboard — never on a field (there is none) and
  // never on the ×: a keyboard user lands where the list starts.
  const first = useRef<HTMLAnchorElement & HTMLButtonElement>(null)
  const go = () => onClose()
  const gate = (l: NavLink) => { onClose(); onGate(l) }
  let firstUsed = false
  const takeFirst = () => { if (firstUsed) return undefined; firstUsed = true; return first }

  const title = who ? (
    <span className="flex items-center gap-3">
      <span aria-hidden className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-100 text-sm font-semibold text-primary-700">
        {who.initials}
      </span>
      <span className="min-w-0">
        {who.name && <span className="block truncate text-base">{who.name}</span>}
        {who.contact && <span className="block truncate text-sm font-normal text-ground-500">{who.contact}</span>}
      </span>
    </span>
  ) : t('common.menu')

  return (
    <Sheet open={open} onClose={onClose} title={title} label={t('common.menu')} initialFocus={first}
      testId="student-menu"
      footer={who ? (
        <button type="button" onClick={() => { void signOutStudent() }}
          className={`${ROW} text-critical-600 hover:bg-critical-50`}>
          {t('header.logout')}
        </button>
      ) : undefined}>
      <nav aria-label={t('common.menu')} className="-mx-2">
        {!who && (
          <button ref={takeFirst()} type="button" onClick={() => { onClose(); router.push('/get-started') }}
            className="mb-2 flex min-h-12 w-full items-center justify-center rounded-lg bg-brand-fill px-4 text-base font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
            {t('header.signUp')}
          </button>
        )}
        {who?.unverified && (
          // TD-454: no "Log in" for her, so this is the way back to the NRIC step (the same sign-in gate).
          <button ref={takeFirst()} type="button" onClick={() => { onClose(); onStudentLogin() }} className={`${ROW} ${ROW_IDLE}`}>
            {t('scholarship.finishSignIn')}
          </button>
        )}
        {groups.map((g, i) => (
          <div key={i} className={i > 0 && !g.label ? 'mt-2 border-t border-ground-100 pt-2' : ''}>
            {g.label && <GroupLabel>{g.label}</GroupLabel>}
            {g.links.map((l) => (
              <Row key={l.href + (l.gate ?? '')} link={l} here={pathname === l.href} onGo={go} onGate={gate}
                first={takeFirst()} />
            ))}
          </div>
        ))}
        {!who && (
          <div>
            <GroupLabel>{t('header.login.label')}</GroupLabel>
            <button type="button" onClick={() => { onClose(); onStudentLogin() }} className={`${ROW} ${ROW_IDLE}`}>
              {t('header.login.student')}
            </button>
            <Link href="/sponsor/login" onClick={go} className={`${ROW} ${ROW_IDLE}`}>{t('header.login.sponsor')}</Link>
            <Link href="/admin/login" onClick={go} className={`${ROW} ${ROW_IDLE}`}>{t('header.login.partner')}</Link>
          </div>
        )}
        <div className="mt-3 border-t border-ground-100 px-2 pt-4">
          <DisplayControls />
        </div>
      </nav>
    </Sheet>
  )
}

/** The desktop avatar's dropdown. Positioned by AppHeader; this is only its card. */
export function AccountPanel({ who, links, pathname, onClose, onFinishSignIn }: {
  who: Who; links: NavLink[]; pathname: string | null; onClose: () => void; onFinishSignIn?: () => void
}) {
  const { t } = useT()
  return (
    <div className="w-72 rounded-xl border border-ground-200 bg-ground-0 py-2 shadow-lg">
      {(who.name || who.contact) && (
        <div className="border-b border-ground-100 px-4 pb-2 pt-1">
          {who.name && <p className="truncate text-sm font-medium text-ground-900">{who.name}</p>}
          {who.contact && <p className="truncate text-xs text-ground-500">{who.contact}</p>}
        </div>
      )}
      <div className="px-2 pt-1">
        {who.unverified && onFinishSignIn && (
          <button type="button" onClick={() => { onClose(); onFinishSignIn() }} className={`${ROW} ${ROW_IDLE}`}>
            {t('scholarship.finishSignIn')}
          </button>
        )}
        {links.map((l) => (
          <Row key={l.href} link={l} here={pathname === l.href} onGo={onClose} onGate={() => {}} />
        ))}
      </div>
      <div className="mx-2 mt-1 border-t border-ground-100 px-2 pb-1 pt-3">
        <DisplayControls />
      </div>
      <div className="mx-2 mt-2 border-t border-ground-100 pt-1">
        <button type="button" onClick={() => { void signOutStudent() }}
          className={`${ROW} min-h-11 text-critical-600 hover:bg-critical-50`}>
          {t('header.logout')}
        </button>
      </div>
    </div>
  )
}

/** Signed out, from `lg`: the theme + language dropdown behind the header's globe button. */
export function DisplayPanel() {
  return (
    <div className="w-80 rounded-xl border border-ground-200 bg-ground-0 p-3 shadow-lg">
      <DisplayControls />
    </div>
  )
}

const CHEVRON = 'M19 9l-7 7-7-7'

function Chevron({ open, className = 'h-4 w-4 text-ground-400' }: { open: boolean; className?: string }) {
  return (
    <svg className={`${className} transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24"
      stroke="currentColor" strokeWidth={2} aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" d={CHEVRON} />
    </svg>
  )
}

/**
 * The desktop row (`lg` up): the nav links, BrightPath ▾, and on the right the avatar's dropdown —
 * or, signed out, the globe "Language" dropdown and Log in ▾ / Sign Up. Hidden below `lg`.
 *
 * ⚠ BRIGHTPATH OPENS ON A CLICK (Mobile M2). It was `group-hover` / `group-focus-within`, which an
 * iPad reached only through Safari's sticky hover — the reason M1a could not adopt Tailwind's
 * `hoverOnlyWhenSupported`. Now every dropdown here is a button with `aria-expanded` whose list
 * exists only while open, closing on a second click, a click or tap outside, Escape or navigation.
 */
export function DesktopBar({ who, incompleteCount }: { who: Who | null; incompleteCount: number }) {
  const { t } = useT()
  const { pathname, b40Links, mainLinks, accountLinks, onGate, studentLogin } = useStudentNav(incompleteCount)
  const [drop, setDrop] = useState<null | 'b40' | 'account' | 'display'>(null)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!drop) return
    const outside = (e: Event) => { if (root.current && !root.current.contains(e.target as Node)) setDrop(null) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setDrop(null) }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', esc)
    }
  }, [drop])
  useEffect(() => { setDrop(null) }, [pathname])

  const toggle = (which: 'b40' | 'account' | 'display') => setDrop((d) => (d === which ? null : which))
  const item = (here: boolean) => `inline-flex min-h-11 items-center gap-1 rounded-lg px-3 text-sm font-medium transition-colors ${
    here ? 'text-primary-600 bg-primary-50' : 'text-ground-600 hover:text-ground-900 hover:bg-ground-50'}`
  // The BrightPath dropdown is "active" on either the student or the sponsor side.
  const b40Active = !!pathname?.startsWith('/scholarship') || pathname === '/sponsor'

  return (
    <div ref={root} className="hidden min-w-0 flex-1 items-center lg:flex">
      <nav className="ml-8 flex items-center gap-1">
        {mainLinks.slice(0, 2).map((l) => (
          <Link key={l.href} href={l.href} className={item(pathname === l.href)}
            aria-current={pathname === l.href ? 'page' : undefined}>{l.label}</Link>
        ))}
        <div className="relative">
          <button type="button" aria-expanded={drop === 'b40'} aria-controls="b40-menu"
            onClick={() => toggle('b40')} className={item(b40Active)}>
            {t('scholarship.nav')}
            <Chevron open={drop === 'b40'} className="h-3.5 w-3.5" />
          </button>
          {drop === 'b40' && (
            <div id="b40-menu" className="absolute left-0 top-full z-20 pt-1">
              <div className="min-w-[210px] rounded-xl border border-ground-100 bg-ground-0 py-1 shadow-lg">
                {b40Links.map((c) => (
                  <Link key={c.href} href={c.href} onClick={() => setDrop(null)}
                    aria-current={pathname === c.href ? 'page' : undefined}
                    className={`flex min-h-11 items-center px-4 text-sm ${
                      pathname === c.href ? 'text-primary-600 bg-primary-50' : 'text-ground-600 hover:bg-ground-50'}`}>
                    {c.label}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
        {mainLinks.slice(2).map((l) => l.gate ? (
          <button key={l.href} type="button" onClick={() => onGate(l)} className={item(false)}>{l.label}</button>
        ) : (
          <Link key={l.href} href={l.href} className={item(pathname === l.href)}
            aria-current={pathname === l.href ? 'page' : undefined}>{l.label}</Link>
        ))}
      </nav>

      <div className="flex-1" />

      <div className="flex items-center gap-3">
        {who ? (
          <div className="relative">
            <button type="button" aria-expanded={drop === 'account'} aria-label={t('header.myProfile')}
              onClick={() => toggle('account')}
              className="flex min-h-11 items-center gap-2 rounded-lg px-2 hover:bg-ground-50">
              <span className="relative">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-sm font-semibold text-primary-600">
                  {who.initials}
                </span>
                {incompleteCount > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-critical-fill text-[10px] font-bold text-critical-fill-ink">
                    {incompleteCount}
                  </span>
                )}
              </span>
              <Chevron open={drop === 'account'} />
            </button>
            {drop === 'account' && (
              <div className="absolute right-0 top-full z-20 mt-1">
                <AccountPanel who={who} links={who.unverified ? [] : accountLinks} pathname={pathname} onClose={() => setDrop(null)}
                  onFinishSignIn={studentLogin} />
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="relative">
              {/* A globe — the sign for "language" that reads in any language. */}
              <button type="button" aria-expanded={drop === 'display'} onClick={() => toggle('display')}
                className="flex min-h-11 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 text-sm font-medium text-ground-600 hover:bg-ground-50">
                <svg className="h-5 w-5 text-ground-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18zm0 0c2.5-2.4 3.75-5.4 3.75-9S14.5 5.4 12 3m0 18c-2.5-2.4-3.75-5.4-3.75-9S9.5 5.4 12 3M3.6 9h16.8M3.6 15h16.8" />
                </svg>
                {t('settings.language')}
                <Chevron open={drop === 'display'} />
              </button>
              {drop === 'display' && (
                <div className="absolute right-0 top-full z-20 mt-1"><DisplayPanel /></div>
              )}
            </div>
            <AuthButtons />
          </>
        )}
      </div>
    </div>
  )
}
