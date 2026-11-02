'use client'

/**
 * Mobile M6a, mounted for mobile-check and the owner's phone review: the REAL admin shell (`AppShell`: the
 * pinned one-row phone bar and the phone menu) around the REAL case list, Guide and FAQ, with fixtures.
 *
 * ⚠ IDENTITY IS SYNTHETIC: an `AdminAuthContext` value — never `AdminAuthProvider` (it would read a real
 * Supabase session) and never a real sign-in. The network is the sandbox's stub (`stubFetch.ts`); every
 * endpoint these screens read is answered here with invented people, and an unanswered one is a 404 the
 * shell treats as furniture. An assignment made here goes nowhere.
 *
 * ⚠ THE ADDRESS: the sandbox lives at `/sandbox/[surface]`, so the shell is told the route it stands on
 * with its sandbox-only `path` (Next's pathname context does not reach a surface — M5 measured it).
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and
 * `mobile-check/targets.ts` reads this file's list too.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { AppShell } from '@/components/admin/AppShell'
import AdminScholarshipList from '@/app/admin/scholarship/page'
import AdminGuidePage from '@/app/admin/guide/page'
import AdminFaqPage from '@/app/admin/faq/page'
import { AdminAuthContext } from '@/lib/admin-auth-context'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

const TOKEN = 'sandbox-not-a-real-token'

const ROLE = {
  is_admin: true, is_super_admin: false, role: 'org_admin', admin_id: 1,
  org_name: 'Yayasan Contoh', owning_org_id: 1, owning_org_name: 'Yayasan Contoh',
  admin_name: 'Pentadbir Contoh', reviewer_profile_complete: true,
}

const row = (id: number, name: string, status: string, bucket: string, qualification: string, merit: number,
  extra: Record<string, unknown> = {}) => ({
  id, name, profile_id: null, cohort_code: 'contoh-2026', qualification, spm_a_count: 6, stpm_pngk: null,
  overall_cgpa: null, referral_source: id % 2 ? 'halatuju' : 'social', merit_score: merit, call_language: '',
  status, bucket, shortlist_reason: '', submitted_at: `2026-10-${20 + id}T08:00:00Z`, profile_completed_at: null,
  assigned_to_id: null, assigned_to_name: null, assignable: true, ready_for_assignment: true, ...extra,
})

const ADMIN_ROUTES: Record<string, () => unknown> = {
  '/api/v1/admin/scholarship/scopes/': () => ({
    organisations: [{ id: 1, code: 'contoh', name: 'Yayasan Contoh' }],
    programmes: [
      { id: 1, code: 'contoh-2026', name: 'Biasiswa Contoh 2026', organisation_id: 1, is_active: true },
      { id: 2, code: 'contoh-sabah', name: 'Bantuan Contoh Sabah', organisation_id: 1, is_active: true },
    ],
  }),
  '/api/v1/admin/scholarship/applications/': () => ({
    count: 4, total_count: 128, total_pages: 6, page: 1, page_size: 25, next: null, previous: null,
    applications: [
      row(1, 'Nurul Aina binti Contoh', 'interviewing', 'A', 'spm', 87.4,
        { assigned_to_id: 7, assigned_to_name: 'Balan Penyemak', call_language: 'ta' }),
      row(2, 'Kavitha a/p Contoh', 'profile_complete', 'A', 'stpm', 91),
      row(3, 'Muhammad Haziq bin Contoh', 'interviewed', 'B', 'spm', 78.2,
        { assigned_to_id: 8, assigned_to_name: 'Devi Penyemak', assignable: false }),
      row(4, 'Tan Contoh Ling', 'submitted', 'B', 'matric', 82.5, { ready_for_assignment: false }),
    ],
  }),
  '/api/v1/admin/scholarship/assignable-admins/': () => ({
    admins: [
      { id: 7, name: 'Balan Penyemak', email: 'balan@sandbox.invalid', role: 'reviewer', languages: ['ms', 'ta'] },
      { id: 8, name: 'Devi Penyemak', email: 'devi@sandbox.invalid', role: 'reviewer', languages: ['en'] },
    ],
    past_assignees: [],
  }),
  '/api/v1/admin/scholarship/source-names/': () => ({ sources: [] }),
}

/** A synthetic org_admin on `path`, inside the real console shell. */
function Console({ path, children }: { path: string; children: ReactNode }) {
  return (
    <AdminAuthContext.Provider value={{
      session: null, token: TOKEN, isLoading: false, isAdminAuthenticated: true, role: ROLE as never,
      refreshRole: async () => {}, photoUrl: null, setPhotoUrl: () => {},
    } as never}>
      <AppShell path={path}>{children}</AppShell>
    </AdminAuthContext.Provider>
  )
}

/** Taps a control once the page has drawn it (opens the menu or a Sheet) — design review only. */
function TapOnce({ selector }: { selector: string }) {
  const [done, setDone] = useState(false)
  useEffect(() => {
    if (done) return
    const id = window.setInterval(() => {
      const el = document.querySelector<HTMLElement>(selector)
      if (el) { el.click(); setDone(true); window.clearInterval(id) }
    }, 100)
    return () => window.clearInterval(id)
  }, [selector, done])
  return null
}

export const ADMIN_SHELL_SURFACES: Surface[] = [
  {
    slug: 'admin-shell-list',
    title: 'Admin — the phone bar and the case list (rows)',
    note: 'Mobile M6a: one pinned 44 px row (Menu · where you are · Search · Notifications · Account); the list '
      + 'as rows that open the case, Filters and Sort on a phone, why an Assign is asleep written under it.',
    routes: ADMIN_ROUTES,
    render: () => <Console path="/admin/scholarship"><AdminScholarshipList /></Console>,
  },
  {
    slug: 'admin-shell-menu',
    title: 'Admin — the phone menu',
    note: 'Mobile M6a: who you are and a 44 px close, the gift and organisation switchers, every destination at '
      + '44 px, then Guide, FAQ, Profile, the theme and Log out.',
    routes: ADMIN_ROUTES,
    render: () => (
      <Console path="/admin/scholarship"><AdminScholarshipList /><TapOnce selector="[data-admin-topbar] > button" /></Console>
    ),
  },
  {
    slug: 'admin-list-filters',
    title: 'Admin — the case list filter Sheet',
    note: 'Mobile M6a: the same filters as the desktop row, in the shared Sheet; the footer names the count and closes.',
    routes: ADMIN_ROUTES,
    render: () => (
      <Console path="/admin/scholarship">
        <AdminScholarshipList /><TapOnce selector="[data-testid=list-phone-tools] button" />
      </Console>
    ),
  },
  {
    slug: 'admin-shell-guide',
    title: 'Admin — the Guide on a phone',
    note: 'Mobile M6a: one chapter chooser above the chapter (the list stays from md); 44 px Previous / Next.',
    routes: ADMIN_ROUTES,
    render: () => <Console path="/admin/guide"><AdminGuidePage /></Console>,
  },
  {
    slug: 'admin-shell-faq',
    title: 'Admin — the FAQ on a phone',
    note: 'Mobile M6a: questions as rows (one box level), 44 px filter chips.',
    routes: ADMIN_ROUTES,
    render: () => <Console path="/admin/faq"><AdminFaqPage /></Console>,
  },
]
