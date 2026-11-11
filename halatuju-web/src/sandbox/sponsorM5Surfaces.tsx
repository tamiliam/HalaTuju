'use client'

/**
 * Mobile M5, mounted for mobile-check and the owner's phone review: the signed-in sponsor portal — the
 * REAL shell (`SponsorShell`: the slim phone header and the sponsor tab bar) around the REAL pages, with
 * fixtures. My Giving, Students (and its filter Sheet), one pool student (and the fund confirm), a
 * supported student with the spending panel, My Account (with the phone's display controls and Log
 * out), and the terms wizard's quiz.
 *
 * ⚠ IDENTITY IS SYNTHETIC: a `SponsorAuthContext` value — never `SponsorAuthProvider` (it would read a
 * real Supabase session) and never a real sign-in. The portal's data is a `SponsorPortalContext` value.
 * The network is the sandbox's stub (`stubFetch.ts`); every sponsor endpoint these pages read is
 * answered here with invented references and numbers, and a write (the fund, a save) is discarded.
 *
 * ⚠ THE ADDRESS: the sandbox lives at `/sandbox/[surface]`, so a surface hands the pages the student they
 * would have through Next's own `useParams()` context, and names the current tab with `SponsorShell`'s
 * sandbox-only `path` (Next's pathname context does not reach a surface — measured).
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and
 * `mobile-check/targets.ts` reads this file's list too.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { PathParamsContext } from 'next/dist/shared/lib/hooks-client-context.shared-runtime'
import SponsorShell, { SponsorCard } from '@/components/sponsor/SponsorShell'
import SponsorTermsWizard from '@/components/sponsors/SponsorTermsWizard'
import MyGivingPage from '@/app/sponsor/(portal)/page'
import StudentsPage from '@/app/sponsor/(portal)/students/page'
import StudentDetailPage from '@/app/sponsor/(portal)/students/[id]/page'
import MyStudentDetailPage from '@/app/sponsor/(portal)/my-students/[id]/page'
import AccountPage from '@/app/sponsor/(portal)/account/page'
import { SponsorAuthContext } from '@/lib/sponsor-auth-context'
import { SponsorPortalContext } from '@/lib/sponsor-portal-context'
import type { SponsorAccount, SponsorPoolCard, SponsorSponsorship } from '@/lib/api'
import { sandboxPool } from './fixtures/sponsor'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

const TOKEN = 'sandbox-not-a-real-token'

const ACCOUNT: SponsorAccount = {
  id: 77, name: 'Puan Contoh Penaja', email: 'penaja.contoh@contoh.invalid', phone: '+60123456789',
  status: 'approved', is_approved: true, profile_complete: true, notify_frequency: 'weekly',
  terms: { terms_version: '2026.1', terms_accepted: true, needs_terms: false, terms_basis: 'accepted' },
}

const card = (o: Partial<SponsorPoolCard>): SponsorPoolCard => ({ ...sandboxPool[0], ...o })
const MINE: SponsorSponsorship[] = [
  { id: 1, status: 'active', amount: '3000.00', offered_at: '2026-03-01T00:00:00Z', accept_deadline: null,
    decided_at: '2026-03-03T00:00:00Z', onboarded: true, semesters: 1,
    student: card({ ref: 'S-CTH-11', state: 'Johor', course: 'Diploma Kejuruteraan Elektrik',
      institution: 'Politeknik Teladan Johor', portfolio_status: 'on_track', progress_state: 'on_track' }) },
  { id: 2, status: 'active', amount: '3000.00', offered_at: '2026-03-01T00:00:00Z', accept_deadline: null,
    decided_at: '2026-03-03T00:00:00Z', onboarded: true, semesters: 2,
    student: card({ ref: 'S-CTH-12', state: 'Pahang', course: 'Diploma Perakaunan',
      institution: 'Kolej Komuniti Teladan', portfolio_status: 'semester_completed',
      progress_state: 'semester_completed', supported_semesters: 6 }) },
  { id: 3, status: 'offered', amount: '3000.00', offered_at: '2026-10-30T00:00:00Z', accept_deadline: '2026-11-13',
    decided_at: null, onboarded: false, semesters: 0,
    student: card({ ref: 'S-CTH-13', state: 'Perak', course: 'Asasi Sains', institution: 'Universiti Teladan' }) },
]

const PORTAL = {
  ready: true, poolUnavailable: false, pool: sandboxPool,
  wallet: { balance: '4500.00', donations: [], sponsorships: MINE },
  impact: { total_given: '9,000', students_supported: 3, students_active: 2, students_graduated: 0,
    semesters_completed: 3, balance: { committed: '6000', completed: '0', available: '4500' } },
  activity: [
    { type: 'funded' as const, ref: 'S-CTH-13', at: '2026-10-30T00:00:00Z' },
    { type: 'semester' as const, ref: 'S-CTH-12', at: '2026-10-20T00:00:00Z' },
  ],
  community: { sponsors: 41, students_supported: 63, students_waiting: 12 },
  statement: {
    donations: [{ amount: '5000.00', reference: 'DN-0001', at: '2026-02-20' }, { amount: '8500.00', reference: 'DN-0002', at: '2026-09-01' }],
    gifts: [{ ref: 'S-CTH-11', amount: '3000.00', at: '2026-03-01' }, { ref: 'S-CTH-12', amount: '3000.00', at: '2026-03-01' }],
    total_in: '13,500.00', total_out: '6,000.00',
  },
  trust: {
    legal_entity: 'Yayasan Contoh Berhad', contact_email: 'amanah@contoh.invalid', trustees: [],
    sources: [{ label: 'Sponsors', amount: '120000' }], uses: [{ label: 'Student awards', amount: '110000' }],
    assurance: { fy: '2025', students_verified: 63, disbursed: '110000', auditor: '' },
    figures_are_illustrative: true, community: { sponsors: 41, students_supported: 63, students_waiting: 12 },
  },
  gradMessages: [],
  referrals: [{ id: 1, invitee_email: 'kawan@contoh.invalid', invitee_name: 'Encik Kawan', note: '', code: 'x',
    status: 'invited' as const, created_at: '2026-10-01', joined_at: null }],
  refreshReferrals: async () => {}, refreshPool: async () => {}, refreshWallet: async () => {},
}

export const SPONSOR_ROUTES: Record<string, () => unknown> = {
  '/api/v1/sponsor/wallet/': () => PORTAL.wallet,
  '/api/v1/sponsor/standing-gift/': () => ({ configured: false, active: false }),
  '/api/v1/sponsor/pool/S-CTH-01/': () => ({ ...sandboxPool[0],   // TD-074: keyed by ref
    anon_profile: 'Anak sulung daripada keluarga petani kecil di Perak. Membaiki motosikal jiran sejak umur 13 tahun.\n\n'
      + 'Mendapat 7A dalam SPM sambil bekerja di gerai keluarga pada hujung minggu.' }),
  '/api/v1/sponsor/my-students/S-CTH-11/': () => ({ ...MINE[0],
    anon_profile: 'Pelajar generasi pertama dari Johor, kini dalam semester dua diploma kejuruteraan elektrik.',
    spending: { promised: '3000.00', released: '1200.00', spent: '940.50', left: '259.50', as_at: '2026-10-28',
      categories: [
        { code: 'food', label: 'Food', total: '412.30' }, { code: 'transport', label: 'Transport', total: '188.00' },
        { code: 'study', label: 'Study', total: '160.20' }, { code: 'phone', label: 'Phone', total: '90.00' },
        { code: 'groceries', label: 'Groceries', total: '90.00' }] } }),
  '/api/v1/sponsor/terms/': () => ({
    terms: TERMS, state: { terms_version: '2026.1', terms_accepted: false, needs_terms: true, terms_basis: '' },
    signed_name: '', accepted_at: null }),
  '/api/v1/sponsor/terms/quiz/': () => ({ version: '2026.1', checkpoints: [
    { order: 1, tag: 'Bahagian 2 · Sumbangan anda', plain: 'Wang anda masuk ke dana biasiswa; program membayar pelajar.',
      question: 'Siapa yang membayar pelajar setiap bulan?', options: ['Saya, secara terus', 'Program, daripada dana biasiswa'],
      correct: 1, why: 'Program membuat dan membayar anugerah; sumbangan anda membiayainya.' },
    { order: 2, tag: 'Bahagian 3 · Identiti', plain: 'Anda melihat rujukan, bukan nama.',
      question: 'Bolehkah anda menghubungi pelajar anda?', options: ['Ya, melalui e-mel', 'Tidak — hanya melalui ucapan terima kasih yang disampaikan program'],
      correct: 1, why: 'Identiti pelajar dilindungi.' }] }),
}

export const TERMS = {
  version: '2026.1', locale_used: 'ms', title: 'Terma penaja', intro: 'Sila baca sebelum anda menaja seorang pelajar.',
  sections: [1, 2, 3].map((n) => ({ order: n, has_quiz: n > 1,
    heading: ['Apa itu tajaan', 'Bagaimana sumbangan anda digunakan', 'Pelajar anda kekal tanpa nama'][n - 1],
    body: 'Tajaan ialah sumbangan kepada dana biasiswa, ditujukan kepada seorang pelajar. Program membuat anugerah dan membayarnya setiap bulan.\n\n'
      + 'Anda tidak akan melihat nama, gambar atau alamat — hanya rujukan dan profil yang telah disemak.' })),
}

/**
 * A synthetic approved sponsor at `path` (and `params`), inside the real shell. `portal` overrides parts of the
 * portal's data (Mobile M8: the trust page with trustees). Exported for `m8Surfaces.tsx`.
 */
export function Portal({ path, params, nav = true, portal, children }: {
  path: string; params?: Record<string, string>; nav?: boolean; portal?: object; children: ReactNode
}) {
  return (
    <PathParamsContext.Provider value={params ?? {}}>
        <SponsorAuthContext.Provider value={{
          session: null, token: TOKEN, isLoading: false, isSignedIn: true, account: ACCOUNT, refreshAccount: async () => {},
        }}>
          <SponsorPortalContext.Provider value={{ ...PORTAL, ...portal } as typeof PORTAL}>
            <SponsorShell nav={nav} path={path}>{children}</SponsorShell>
          </SponsorPortalContext.Provider>
        </SponsorAuthContext.Provider>
    </PathParamsContext.Provider>
  )
}

/** Taps a control once the page has drawn it (opens a Sheet, starts the quiz) — design review only. */
export function TapOnce({ selector }: { selector: string }) {
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

export const SPONSOR_PORTAL_SURFACES: Surface[] = [
  {
    slug: 'sponsor-giving',
    title: 'Sponsor — My Giving (tabs, sections)',
    note: 'Mobile M5: the slim phone header and the sponsor tab bar; My Giving as sections; the students '
      + 'you support as rows with the 12 px journey line (was 9 px words under dots).',
    routes: SPONSOR_ROUTES,
    render: () => <Portal path="/sponsor"><MyGivingPage /></Portal>,
  },
  {
    slug: 'sponsor-students',
    title: 'Sponsor — Students (the Filters button)',
    note: 'Mobile M5: the four selects become one 44 px Filters button on a phone; the cards are the one box level.',
    routes: SPONSOR_ROUTES,
    render: () => <Portal path="/sponsor/students"><StudentsPage /></Portal>,
  },
  {
    slug: 'sponsor-filters',
    title: 'Sponsor — the Students filter Sheet',
    note: 'Mobile M5: the filter Sheet — chips per facet, a tap applies at once, the footer counts and closes.',
    routes: SPONSOR_ROUTES,
    render: () => (
      <Portal path="/sponsor/students"><StudentsPage /><TapOnce selector="[data-testid=sponsor-filters-button]" /></Portal>
    ),
  },
  {
    slug: 'sponsor-pool-student',
    title: 'Sponsor — one pool student (the fund bar)',
    note: 'Mobile M5: sections, and the sticky "Fully fund" bar with the balance — a page bar, so the tabs give way.',
    routes: SPONSOR_ROUTES,
    render: () => <Portal path="/sponsor/students/S-CTH-01" params={{ id: 'S-CTH-01' }}><StudentDetailPage /></Portal>,
  },
  {
    slug: 'sponsor-fund-confirm',
    title: 'Sponsor — the fund confirm (cannot be swiped away)',
    note: 'Mobile M5: the one confirm for both widths, `dismissible={false}`; the amount is the server’s.',
    routes: SPONSOR_ROUTES,
    render: () => (
      <Portal path="/sponsor/students/S-CTH-01" params={{ id: 'S-CTH-01' }}>
        <StudentDetailPage /><TapOnce selector="[data-testid=fund-bar] button" />
      </Portal>
    ),
  },
  {
    slug: 'sponsor-my-student',
    title: 'Sponsor — a supported student (spending)',
    note: 'Mobile M5: one box level — the banner edge to edge, commitment and spending as sections, 12 px labels.',
    routes: SPONSOR_ROUTES,
    render: () => <Portal path="/sponsor/my-students/S-CTH-11" params={{ id: 'S-CTH-11' }}><MyStudentDetailPage /></Portal>,
  },
  {
    slug: 'sponsor-account',
    title: 'Sponsor — My Account (display, language, Log out)',
    note: 'Mobile M5: sections; on a phone the theme, the language and Log out live at the end of this page.',
    routes: SPONSOR_ROUTES,
    render: () => <Portal path="/sponsor/account"><AccountPage /></Portal>,
  },
  {
    slug: 'sponsor-terms-quiz',
    title: 'Sponsor — the terms quiz (full width, sticky Next)',
    note: 'Mobile M5: the wizard runs the full width on a phone; progress and Next sit in a sticky page bar.',
    routes: SPONSOR_ROUTES,
    render: () => (
      <Portal path="/sponsor" nav={false}>
        <SponsorCard>
          <SponsorTermsWizard token={TOKEN} accountName={ACCOUNT.name || ''} onAccepted={() => {}} />
        </SponsorCard>
        <TapOnce selector="[data-testid=terms-start]" />
      </Portal>
    ),
  },
]
