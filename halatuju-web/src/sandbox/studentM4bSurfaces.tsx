'use client'

/**
 * Mobile M4b, mounted for mobile-check and the owner's phone review: the student tab bar signed in and
 * signed out, and the pages swept to one box level that a stranger cannot open — the dashboard, the
 * profile and the settings page — each the REAL page with fixtures.
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and
 * `mobile-check/targets.ts` reads this file's list too. Identity is a synthetic `AuthContext` value —
 * never `AuthProvider` (it would mint a real anonymous Supabase user) and never a real sign-in. The
 * network is the sandbox's stub (`stubFetch.ts`); every endpoint these pages read is answered here,
 * with invented people and numbers. The results the dashboard reads from this device are written into
 * storage DURING render, before the page's own effects read them.
 */
import { useState, type ReactNode } from 'react'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import DashboardPage from '@/app/dashboard/page'
import ProfilePage from '@/app/profile/page'
import SettingsPage from '@/app/settings/page'
import { AuthContext } from '@/lib/auth-context'
import { KEY_EXAM_TYPE, KEY_GRADES, KEY_PROFILE, rememberBursaryFile } from '@/lib/storage'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

const GRADES = { BM: 'A', BI: 'A-', MAT: 'B+', SEJ: 'B', PI: 'A', SN: 'B+', MT: 'B', FIZ: 'C+', KIM: 'B' }

/** A signed-in student, synthetic: results on her server profile so the pages' guards let her in. */
function SignedIn({ bursary = false, children }: { bursary?: boolean; children: ReactNode }) {
  // Written during render (not in an effect): a child's effect runs BEFORE this component's, and the
  // dashboard reads its results from storage in one.
  useState(() => {
    try {
      localStorage.setItem(KEY_GRADES, JSON.stringify(GRADES))
      localStorage.setItem(KEY_PROFILE, JSON.stringify({ gender: 'female', nationality: 'malaysian' }))
      localStorage.setItem(KEY_EXAM_TYPE, 'spm')
    } catch { /* storage blocked: the page shows its empty state */ }
    rememberBursaryFile(bursary)
    return null
  })
  return (
    <AuthContext.Provider value={{
      status: 'ready', isAuthenticated: true, isAnonymous: false, hasSession: true, isLoading: false,
      token: 'sandbox-not-a-real-token', showAuthGate: () => {}, refreshProfile: async () => {},
      profile: { grades: GRADES, results_held: 'spm' },
      session: { user: { email: 'pelajar@contoh.invalid', user_metadata: { full_name: 'Kavitha Raman' } } },
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

function SignedOut({ children }: { children: ReactNode }) {
  useState(() => { rememberBursaryFile(false); return null })
  return (
    <AuthContext.Provider value={{
      status: 'anonymous', isAuthenticated: false, isAnonymous: true, hasSession: false, isLoading: false,
      token: null, profile: null, session: null, showAuthGate: () => {},
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

/** A page under the header long enough to scroll, ending in the footer: the tabs must never cover it. */
function Filler() {
  return (
    <div className="bg-ground-50">
      <div className="container mx-auto space-y-4 px-4 py-6">
        {Array.from({ length: 8 }, (_, i) => (
          <p key={i} className="text-sm text-ground-600">
            Kursus {i + 1}: maklumat ringkas tentang kursus, syarat kemasukan dan tempat belajar.
          </p>
        ))}
      </div>
      <AppFooter />
    </div>
  )
}

const course = (id: string, name: string, pathway: string, level: string, label: string, color: string, inst: string, state: string) => ({
  course_id: id, course_name: name, level, field: '', field_key: '', source_type: pathway, pathway_type: pathway,
  qualification: 'SPM', merit_cutoff: 70, student_merit: 78, merit_label: label, merit_color: color,
  institution_name: inst, institution_state: state, institution_count: 1,
})

/** What `/api/v1/eligibility/check/` answers for her results (invented). */
const ELIGIBILITY = {
  eligible_courses: [
    course('SB-ASASI-1', 'Asasi Sains Hayat', 'asasi', 'Asasi', 'High', 'green', 'Universiti Malaya', 'W.P. Kuala Lumpur'),
    course('SB-POLY-1', 'Diploma Kejuruteraan Mekanikal', 'poly', 'Diploma', 'High', 'green', 'Politeknik Ungku Omar', 'Perak'),
    course('SB-POLY-2', 'Diploma Teknologi Maklumat (Teknologi Digital)', 'poly', 'Diploma', 'Fair', 'amber', 'Politeknik Sultan Abdul Halim Mu’adzam Shah', 'Kedah'),
    course('SB-KK-1', 'Sijil Teknologi Elektrik', 'kkom', 'Sijil', 'Fair', 'amber', 'Kolej Komuniti Selayang', 'Selangor'),
    course('SB-UA-1', 'Asasi Pengurusan', 'university', 'Asasi', 'Low', 'red', 'Universiti Utara Malaysia', 'Kedah'),
  ],
  stats: {}, pathway_stats: {},
  insights: { merit_summary: { high: 2, fair: 2, low: 1, no_data: 0 } },
}

/** What `/api/v1/profile/` answers (invented; one family field left empty, so a section shows "to fill"). */
const PROFILE = {
  name: 'Kavitha Raman', gender: 'female', nationality: 'malaysian', bumiputera: false,
  identity_verified: true, nric_locked: true, colorblind: false, disability: false, preferred_state: 'Selangor',
  address: 'No 12, Jalan Melur 3, Taman Bunga', postal_code: '43000', city: 'Kajang', email: 'pelajar@contoh.invalid',
  household_income: 2800, household_size: 5, father_name: 'Raman a/l Muthu', father_occupation: 'driver',
  mother_name: '', mother_occupation: '', other_family_members: [], siblings_in_school: 2, siblings_in_tertiary: 0,
  contact_phone: '0123456789', contact_phone_verified: true, contact_email: 'pelajar@contoh.invalid',
  contact_email_verified: true, school: 'SMK Taman Bunga', grades: GRADES, results_held: 'spm',
}

const PAGE_ROUTES = {
  '/api/v1/eligibility/check/': () => ELIGIBILITY,
  '/api/v1/profile/': () => PROFILE,
  '/api/v1/saved-courses/': () => ({ saved_courses: [] }),
  '/api/v1/reports/': () => ({ reports: [] }),
  '/api/v1/scholarship/applications/': () => ({ total_count: 0, applications: [] }),
}

export const STUDENT_PAGE_SURFACES: Surface[] = [
  {
    slug: 'tab-bar-signed-in',
    title: 'Student tab bar — signed in, with a bursary file',
    note: 'The phone\'s four tabs (Mobile M4b): Dashboard, Explore, Saved and the programme (the organisation’s short name), which opens My '
      + 'Bursary for her. Her profile stays the header\'s avatar; the menu keeps every destination. The page '
      + 'ends in the footer, never under the bar. Hidden while she types and wherever a page has its own bar.',
    render: () => <SignedIn bursary><AppHeader /><Filler /></SignedIn>,
  },
  {
    slug: 'tab-bar-signed-out',
    title: 'Student tab bar — signed out',
    note: 'A visitor sees the same four tabs; Saved opens the sign-in sheet (or onboarding before any '
      + 'results), the programme tab the bursary landing. The header keeps Log in and the menu.',
    render: () => <SignedOut><AppHeader /><Filler /></SignedOut>,
  },
  {
    slug: 'dashboard',
    title: 'Dashboard — SPM results, five courses',
    note: 'Rule 15 on a phone: the summary is a plain section on a 16 px gutter, the pathway pills are 44 px, '
      + 'the course cards sit straight on the page. The tab bar is on Dashboard.',
    render: () => <SignedIn><DashboardPage /></SignedIn>,
    routes: PAGE_ROUTES,
  },
  {
    slug: 'profile',
    title: 'My Profile — sections, not cards',
    note: 'Rule 15: every part of her profile is a full-width section with its heading and a 44 px Edit, the '
      + 'particulars divided by hairlines. The family section has one field still to fill.',
    render: () => <SignedIn><ProfilePage /></SignedIn>,
    routes: PAGE_ROUTES,
  },
  {
    slug: 'settings',
    title: 'Settings — sections, not cards',
    note: 'Language, theme, clearing this device\'s data and the version, as plain sections on a phone.',
    render: () => <SignedIn><SettingsPage /></SignedIn>,
    routes: PAGE_ROUTES,
  },
]
