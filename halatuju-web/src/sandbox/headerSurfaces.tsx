'use client'

/**
 * The student shell, mounted for mobile-check and the owner's phone review (Mobile M2).
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and
 * `mobile-check/targets.ts` reads this file's list too. Every surface mounts the REAL component.
 *
 * Signed-in surfaces get their identity from `AuthContext.Provider` with a synthetic value — never
 * `AuthProvider` (it would mint a real anonymous Supabase user) and never a real sign-in. The menu
 * surfaces open the phone menu on mount (`defaultMenuOpen`); its × or backdrop closes it, the menu
 * button reopens it. mobile-check runs each at 360 and 390 px in English, Malay and Tamil.
 */
import { useEffect, useState, type ReactNode } from 'react'
import AppHeader from '@/components/AppHeader'
import FlowHeader from '@/components/FlowHeader'
import StpmSubjectRow, { StpmCountTag } from '@/components/StpmSubjectRow'
import { AuthContext } from '@/lib/auth-context'
import { rememberBursaryFile } from '@/lib/storage'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode }

/** A signed-in student, synthetic. Only the fields the header reads are filled. */
function SignedIn({ bursary, children }: { bursary: boolean; children: ReactNode }) {
  // The "has a bursary file" hint is device storage; set it for this surface and tell the header.
  useEffect(() => { rememberBursaryFile(bursary) }, [bursary])
  return (
    <AuthContext.Provider value={{
      status: 'ready', isAuthenticated: true, isAnonymous: false, hasSession: true,
      token: 'sandbox-not-a-real-token', profile: null, showAuthGate: () => {},
      session: { user: { email: 'pelajar@contoh.invalid', user_metadata: { full_name: 'Kavitha Raman' } } },
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

/** Signed out: the gate is a no-op here (the real one is not mounted in the sandbox). */
function SignedOut({ children }: { children: ReactNode }) {
  useEffect(() => { rememberBursaryFile(false) }, [])
  return (
    <AuthContext.Provider value={{
      status: 'anonymous', isAuthenticated: false, isAnonymous: true, hasSession: false,
      token: null, profile: null, session: null, showAuthGate: () => {},
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

/** Something under the header, so the bar is seen as it sits on a page. */
function Page({ children }: { children: ReactNode }) {
  return <div className="min-h-[60dvh] bg-ground-50">{children}<div className="h-96" /></div>
}

const GRADE = 'w-24 shrink-0 rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 text-sm font-medium text-primary-700'
const SUBJECT = 'w-full min-w-0 rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-sm'

/** The STPM rows as a phone shows them once a PNGK is known: counted, always, and not counted. */
function StpmRows() {
  const [rows, setRows] = useState(['Matematik (T)', 'Fizik', 'Kimia', 'Biologi'])
  const grades: Record<string, string> = { 'Matematik (T)': 'A', Fizik: 'B+', Kimia: 'B', Biologi: 'C' }
  const select = (value: string, options: string[], cls: string) => (
    <select className={cls} value={value} onChange={() => {}}>{options.map((o) => <option key={o}>{o}</option>)}</select>
  )
  return (
    <div className="mx-auto max-w-3xl space-y-3 px-4 py-6">
      <StpmSubjectRow
        subject={<span className="font-medium text-ground-900">Pengajian Am</span>}
        grade={select('A-', ['A-'], GRADE)}
        tag={<StpmCountTag kind="always" />} />
      {rows.map((s) => (
        <StpmSubjectRow key={s}
          subject={select(s, [s], SUBJECT)}
          grade={select(grades[s], [grades[s]], GRADE)}
          tag={<StpmCountTag kind={s === 'Biologi' ? 'notCounted' : 'counted'} />}
          onRemove={() => setRows((r) => r.filter((x) => x !== s))} />
      ))}
    </div>
  )
}

export const HEADER_SURFACES: Surface[] = [
  {
    slug: 'header-signed-out',
    title: 'Student header — signed out',
    note: 'The one student header (Mobile M2) as a visitor sees it: logo, Log in, the menu button — '
      + 'one row in every language at 360 px. From lg, the nav row; the bursary menu opens on a click.',
    render: () => <SignedOut><Page><AppHeader /></Page></SignedOut>,
  },
  {
    slug: 'header-signed-out-menu',
    title: 'Student header — signed-out menu open',
    note: 'The phone menu in the shared Sheet: Sign up first, the destinations, the three logins, '
      + 'then theme and language. Each item once; the list scrolls inside the sheet.',
    render: () => <SignedOut><Page><AppHeader defaultMenuOpen /></Page></SignedOut>,
  },
  {
    slug: 'header-signed-in-menu',
    title: 'Student header — signed-in menu open',
    note: 'A signed-in student without a bursary file: her name heads the sheet, every destination '
      + 'once, profile and settings, theme and language, Log out pinned at the foot.',
    render: () => <SignedIn bursary={false}><Page><AppHeader defaultMenuOpen /></Page></SignedIn>,
  },
  {
    slug: 'header-signed-in-menu-bursary',
    title: 'Student header — signed-in menu open, with My Bursary',
    note: 'The same student once the pages have seen her bursary file: My Bursary joins the '
      + 'bursary group. The longest list the menu shows.',
    render: () => <SignedIn bursary><Page><AppHeader defaultMenuOpen /></Page></SignedIn>,
  },
  {
    slug: 'onboarding-stepper',
    title: 'Onboarding header — step 2 of 3',
    note: 'The logo never shrinks; "Step 2 of 3" sits over its bars. Malay is the longest '
      + '("Langkah 2 daripada 3"), which used to squeeze the logo to 44 px at 360.',
    render: () => <Page><FlowHeader step={2} /></Page>,
  },
  {
    slug: 'stpm-grade-rows',
    title: 'STPM grade rows — with the "not counted" tag',
    note: 'Two lines on a phone: the subject and its 44 px remove button, then the grade and whether '
      + 'it counts. The long "not counted" tag wraps under the grade instead of crushing the subject.',
    render: () => <StpmRows />,
  },
]
