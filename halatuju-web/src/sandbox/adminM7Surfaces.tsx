'use client'

/**
 * Mobile M7a, mounted for mobile-check and the owner's phone review: the REAL "Can" admin screens inside the REAL
 * console shell, with invented fixtures — the scholar file, the scholars list, Announcements (a table as rows),
 * the sponsor terms list, the payment run, student detail, organisation settings, a request and the Requests list;
 * sprint P1 adds the scholar file's Activity tab on its own (the file's tabs are internal state, a phone's a <select>).
 *
 * ⚠ IDENTITY IS SYNTHETIC (an `AdminAuthContext` value, never the provider, never a sign-in), and the network is
 * the sandbox stub: every write here goes nowhere. The address is the shell's sandbox-only `path`; a detail page
 * reads its id from Next's params, so the surface supplies them (`PathParamsContext`, the context `useParams`
 * reads — Next 14).
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and `mobile-check/targets.ts`
 * reads this file's list too.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { PathParamsContext } from 'next/dist/shared/lib/hooks-client-context.shared-runtime'
import { AppShell } from '@/components/admin/AppShell'
import { AdminAuthContext } from '@/lib/admin-auth-context'
import ScholarsPage from '@/app/admin/scholars/page'
import ScholarFilePage from '@/app/admin/scholars/[id]/page'
import SponsorsPage from '@/app/admin/sponsors/page'
import PaymentRunPage from '@/app/admin/payments/[id]/page'
import AnnouncementsPage from '@/app/admin/programme/announcements/page'
import StudentDetailPage from '@/app/admin/students/[id]/page'
import OrgSettingsPage from '@/app/admin/organisation/settings/page'
import RequestDetailPage from '@/app/admin/requests/[id]/page'
import RequestsPage from '@/app/admin/requests/page'
import ContractsPage from '@/app/admin/contracts/page'
import ContractEditorPage from '@/app/admin/contracts/[id]/page'
import ScholarActivity from '@/components/admin/ScholarActivity'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

const ORG_ADMIN = {
  is_admin: true, is_super_admin: false, role: 'org_admin', admin_id: 1,
  org_name: 'Yayasan Contoh', owning_org_id: 1, owning_org_name: 'Yayasan Contoh',
  admin_name: 'Pentadbir Contoh', reviewer_profile_complete: true,
  permissions: ['review', 'qc', 'see_all', 'payments', 'spending', 'sponsors'],
}
const SUPER = { ...ORG_ADMIN, is_super_admin: true, role: 'super' }

const SCOPES: Record<string, () => unknown> = {
  '/api/v1/admin/scholarship/scopes/': () => ({
    organisations: [{ id: 1, code: 'contoh', name: 'Yayasan Contoh' }],
    programmes: [{ id: 1, code: 'contoh-2026', name: 'Biasiswa Contoh 2026', organisation_id: 1, is_active: true }],
  }),
}

function Console({ path, role = ORG_ADMIN, params, children }: {
  path: string; role?: Record<string, unknown>; params?: Record<string, string>; children: ReactNode
}) {
  const inner = (
    <AdminAuthContext.Provider value={{
      session: null, token: 'sandbox-not-a-real-token', isLoading: false, isAdminAuthenticated: true, role: role as never,
      refreshRole: async () => {}, photoUrl: null, setPhotoUrl: () => {},
    } as never}>
      <AppShell path={path}>{children}</AppShell>
    </AdminAuthContext.Provider>
  )
  return params ? <PathParamsContext.Provider value={params}>{inner}</PathParamsContext.Provider> : inner
}

/** Taps a control once the page has drawn it (opens a tab) — design review only. */
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

const scholarRow = (id: number, name: string, substate: string, standing: string) => ({
  id, name, gift: { code: 'contoh-2026', name: 'Biasiswa Contoh 2026' },
  course: 'Ijazah Sarjana Muda Kejuruteraan Mekanikal dengan Kepujian', institution: 'Universiti Teknologi Malaysia',
  status: 'maintenance', maintenance_substate: substate, is_on_hold: substate === 'on_hold',
  latest_result: { cgpa: '3.42', semester: 'Semester 2 2025/26', at: '2026-08-01' }, pending_review: id === 2,
  standing, next_due: '2026-12-15', mentor: id % 2 ? 'Balan Mentor' : null, asked_for_help: id === 3,
  mentor_concerned: false, last_activity_at: '2026-10-28T08:00:00Z',
})
const SCHOLAR_FILE = {
  ...scholarRow(1, 'Kavitha a/p Contoh', 'on_track', 'performing'),
  in_maintenance: true, has_file: true, closure_reason: '', awarded_at: '2026-01-10', vircle_activated_at: '2026-02-01',
  closed_at: null,
  money: { award_amount: '12000.00', paid_to_date: '4800.00', remaining: '7200.00', last_payment: { amount: '400.00', at: '2026-10-05' } },
  contract: { exists: true, status: 'executed' }, thresholds: { minimum: '2.50', failing: '2.00' },
  mentor: { name: 'Balan Mentor', since: '2026-03-01', meetings: 4 },
  asked_for_help: { university: false, scholarship: true, flagged: false },
  letters: { count: 3, awaiting: 1, overdue: 0, latest: [
    { kind: 'general', subject: 'Selamat datang ke Biasiswa Contoh', issued_at: '2026-01-12', state: 'acknowledged' },
    { kind: 'discipline', subject: 'Notis keputusan semester', issued_at: '2026-08-10', state: 'awaiting' },
  ] },
  controls: { can_review_results: true, can_set_substate: true, can_hold: true, close_reasons: ['graduated', 'withdrew'], close_refusal: '' },
}

/** Sprint P1: a scholar's activity log — staff with and without a photo, the scholar, a fully automatic row,
 *  an email that matches nobody, a call, a long note and a staff-only one. Newest first, as the server pages it;
 *  each time is relative to the run (so it reads "2 hours ago", not a date years back). */
const ago = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString()
const STAFF_A = { name: 'Pentadbir Contoh', photo_url: null, kind: 'staff' }
const STAFF_B = { name: 'Siti Pegawai Contoh', photo_url: null, kind: 'staff' }
const entry = (id: number, hours: number, kind: string, extra: Record<string, unknown>) => ({
  id, kind, event: '', body: '', meta: {}, actor_email: '', actor: null, internal: false, created_at: ago(hours), ...extra })
const ACTIVITY_ROWS = [
  entry(12, 2, 'note', { body: 'Spoke to her about the second-semester timetable. She will send the slip on Friday.',
    actor: STAFF_A, internal: true }),
  entry(11, 20, 'call', { body: 'Rang her guardian; the address on file is current.', actor: STAFF_B }),
  entry(10, 30, 'system', { event: 'letter_acknowledged', meta: { subject: 'Notis keputusan semester' },
    actor: { name: 'Kavitha a/p Contoh', photo_url: null, kind: 'scholar' } }),
  entry(9, 50, 'system', { event: 'substate_changed', meta: { old: 'probation', new: 'on_track' }, actor: STAFF_A }),
  entry(8, 120, 'system', { event: 'payment_released', meta: { amount: '400.00', run: 'RUN-2026-10' } }),
  entry(7, 200, 'note', { body: 'Transferred from the old record.',
    actor: { name: 'former.officer@contoh.invalid', photo_url: null, kind: 'unknown' } }),
  entry(6, 400, 'system', { event: 'results_overdue', meta: { due_on: '2026-09-30' } }),
  entry(5, 900, 'note', { body: 'Met at the campus. A long note so the row wraps on a phone: she is managing the '
    + 'course load, has joined the study group the faculty runs on Wednesdays, and asked about the hostel fee.', actor: STAFF_B }),
]
const ACTIVITY_COUNTS = { all: 14, notes: 7, system: 7 }
const activityPage = (size: number) => () => ({
  count: 14, page: 1, page_size: size, counts: ACTIVITY_COUNTS, results: ACTIVITY_ROWS.slice(0, size) })

const runItem = (id: number, name: string, extra: Record<string, unknown> = {}) => ({
  id, application_id: id + 10, name, nric: 'XXXXXX-XX-XXXX', vircle_id: `VC-00${id}8812`, activated: id !== 2,
  award_amount: '12000.00', paid_to_date: '4800.00', amount: '400.00', credit_applied: id === 1 ? '50.00' : '0.00',
  included: true, exclude_reason: '', on_hold: false, ...extra,
})
const PAYMENT_RUN = {
  vircle_email: 'payments@sandbox.invalid', id: 1, reference: 'PR-2026-11-001', payment_date: '2026-11-05',
  period_month: '2026-11-01', status: 'draft', programme: { id: 1, code: 'contoh-2026', name: 'Biasiswa Contoh 2026' },
  note: '', drive_file_url: '', created_by: 'Pentadbir Contoh', created_at: '2026-11-01T00:00:00Z', admin_signed: null,
  finance_signed: null, finance_check_required: true, check_step_required: true, your_step: 'sign',
  approver_fallback: false, can_prepare: true, org_admin_signed: null,
  items: [runItem(1, 'Kavitha a/p Contoh'), runItem(2, 'Muhammad Haziq bin Contoh'),
    runItem(3, 'Tan Contoh Ling', { included: false, exclude_reason: 'Keputusan semester belum diterima' })],
  skipped: [{ application_id: 30, name: 'Nurul Aina binti Contoh', nric: 'XXXXXX-XX-XXXX', reasons: ['no_wallet'] }],
  students: 2, total: '800.00',
}

const announcement = (id: number, title: string, status: string) => ({
  id, title, body: 'Sila hantar keputusan semester anda sebelum 15 Disember.', status, pinned: id === 1,
  programme: id === 2 ? { code: 'contoh-2026', name: 'Biasiswa Contoh 2026' } : null, audience_count: 42, read_count: 17,
  email_requested: true, emailed_at: '2026-10-20T00:00:00Z', emailed_count: 42, email_switched_off: false,
  publish_at: null, published_at: '2026-10-20T00:00:00Z', edited_at: null, withdrawn_at: null,
  author: { email: 'pentadbir@sandbox.invalid', name: 'Pentadbir Contoh', role: 'org_admin' },
  created_at: '2026-10-19T00:00:00Z', can_delete: status === 'draft', can_withdraw: status === 'published',
})

const STUDENT = {
  supabase_user_id: 'u-1', name: 'Kavitha a/p Contoh', nric: 'XXXXXX-XX-XXXX', angka_giliran: 'JX123A456',
  gender: 'female', nationality: 'malaysian', contact_phone: '0123456789', address: '12, Jalan Contoh 3, Taman Contoh',
  postal_code: '43000', city: 'Kajang', school: 'SMK Contoh', household_income: 2400, household_size: 5,
  colorblind: 'no', disability: 'no', exam_type: 'spm',
  grades: { bm: 'A', bi: 'A-', math: 'A', sci: 'B+', hist: 'A', addmath: 'A-', phy: 'B+', chem: 'A' },
  stpm_grades: {}, stpm_cgpa: null, muet_band: null, student_signals: { field_interest: { engineering: 3, medicine: 1 } },
  preferred_state: 'Selangor', financial_pressure: 'high', travel_willingness: 'yes', referral_source: 'halatuju',
  org_name: 'Yayasan Contoh', created_at: '2026-03-01T00:00:00Z',
  saved_courses: [{ course_id: 'POLY-DIP-019', name: 'Diploma Kejuruteraan Mekanikal' }],
}

const REQUEST = {
  id: 7, kind: 'feature', title: 'Tambah laporan bulanan untuk penaja', component: 'sponsors', urgency: 'nice_to_have',
  description: 'Penaja kami mahu satu ringkasan bulanan: pelajar yang ditaja, wang yang dikeluarkan dan keputusan semester.',
  steps_to_reproduce: '', status: 'quoted',
  comments: [{ id: 1, author_name: 'Pentadbir Contoh', author_role: 'org_admin', author_kind: 'org', body: 'Boleh mula selepas cuti?',
    shared: true, created_at: '2026-10-29T08:00:00Z' }],
  attachments: [], quote_hours: '6.0', quote_note: 'Satu laporan PDF, dihantar pada 1 hb setiap bulan.',
  quoted_at: '2026-10-30T08:00:00Z', approved_at: null, approved_by_name: '', approved_by_role: '', scheduled_for: null,
  decline_reason: '', created_at: '2026-10-28T08:00:00Z', updated_at: '2026-10-30T08:00:00Z',
  submitted_by_name: 'Pentadbir Contoh',
}
const requestRow = (id: number, title: string, status: string, tags: string[] = []) => ({
  id, title, kind: 'feature', status, submitted_by_name: 'Pentadbir Contoh', created_at: '2026-10-2' + id + 'T08:00:00Z', tags,
})

export const ADMIN_CAN_SURFACES: Surface[] = [
  {
    slug: 'm7-scholars',
    title: 'Admin — Scholars list',
    note: 'Mobile M7a: the scholars list on a phone (its own phone cards; 44 px tabs).',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/scholars/': () => ({
      summary: { in_programme: 42, on_hold: 2, probation: 3, ready_to_close: 1, closed: 7, below_minimum: 4,
        results_overdue: 5, no_mentor: 6, asked_for_help: 2, mentor_concerned: 1 },
      count: 4, page: 1, page_size: 25,
      results: [scholarRow(1, 'Kavitha a/p Contoh', 'on_track', 'performing'),
        scholarRow(2, 'Muhammad Haziq bin Contoh', 'probation', 'underperforming'),
        scholarRow(3, 'Tan Contoh Ling', 'on_hold', 'failing'), scholarRow(4, 'Nurul Aina binti Contoh', 'ready_to_close', 'awaiting_review')],
    }) },
    render: () => <Console path="/admin/scholars"><ScholarsPage /></Console>,
  },
  {
    slug: 'm7-scholar-file',
    title: 'Admin — the scholar file',
    note: 'Mobile M7a: sections, not cards; the nine tabs are ONE chooser on a phone; the money as rows; the status '
      + 'read-only with a note (owner).',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/scholars/1/': () => SCHOLAR_FILE,
      '/api/v1/admin/scholarship/scholars/1/activity/': activityPage(6) },
    render: () => <Console path="/admin/scholars/1" params={{ id: '1' }}><ScholarFilePage /></Console>,
  },
  {
    slug: 'p1-scholar-activity',
    title: 'Admin — the scholar file\'s Activity tab',
    note: 'Sprint P1: oldest at the top, the box below, a list that scrolls inside itself (55dvh on a phone), '
      + '"Show older", the All · Notes · System filter (44 px), names and initials, and the one-line composer.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/scholars/1/activity/': activityPage(20) },
    render: () => (
      <Console path="/admin/scholars/1" params={{ id: '1' }}>
        <div className="max-w-3xl"><ScholarActivity id={1} token="sandbox-not-a-real-token" /></div>
      </Console>
    ),
  },
  {
    slug: 'm7-announcements',
    title: 'Admin — Announcements (a table as rows)',
    note: 'Mobile M7a: the same table restacked as rows below md (TableFrame phoneRows); 44 px tabs and actions.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/announcements/': () => ({
      organisation: { code: 'contoh', name: 'Yayasan Contoh' },
      announcements: [announcement(1, 'Hantar keputusan semester sebelum 15 Disember', 'published'),
        announcement(2, 'Bengkel kewangan peribadi untuk penerima biasiswa', 'published')],
      counts: { draft: 1, scheduled: 1, published: 2, withdrawn: 0 },
      audiences: [{ programme: null, name: 'Semua', count: 42 }, { programme: 'contoh-2026', name: 'Biasiswa Contoh 2026', count: 42 }],
      email_switch_on: true, limits: { title: 120, body: 4000 },
    }) },
    render: () => <Console path="/admin/programme/announcements"><AnnouncementsPage /></Console>,
  },
  {
    slug: 'm7-sponsor-terms',
    title: 'Admin — Sponsors, the Terms tab',
    note: 'Mobile M7a: the terms versions as rows on a phone (it scrolled 640 px sideways).',
    routes: { ...SCOPES, '/api/v1/admin/sponsors/': () => ({ sponsors: [] }),
      '/api/v1/admin/scholarship/sponsor-terms/': () => ({
        versions: [
          { id: 2, version: 'v3', status: 'active', title_en: 'Sponsor terms', languages_available: ['en', 'ms', 'ta'],
            section_count: 9, created_by_email: 'pentadbir@sandbox.invalid', published_by_email: 'pengarah.contoh@sandbox.invalid',
            published_at: '2026-08-01T00:00:00Z', archived_at: null, created_at: '2026-07-20T00:00:00Z', updated_at: '2026-08-01T00:00:00Z' },
          { id: 1, version: 'v2', status: 'archived', title_en: 'Sponsor terms', languages_available: ['en', 'ms'],
            section_count: 8, created_by_email: 'pentadbir@sandbox.invalid', published_by_email: 'pentadbir@sandbox.invalid',
            published_at: '2026-03-01T00:00:00Z', archived_at: '2026-08-01T00:00:00Z', created_at: '2026-02-20T00:00:00Z', updated_at: '2026-08-01T00:00:00Z' },
        ], active_version: 'v3', sponsor_count: 14,
      }) },
    render: () => (
      <Console path="/admin/sponsors"><SponsorsPage /><TapOnce selector="[role=tab]:nth-child(3)" /></Console>
    ),
  },
  {
    slug: 'm7-payment-run',
    title: 'Admin — a payment run',
    note: 'Mobile M7a (layout only): the rows divided, not boxed; 12 px text; 44 px sign-off buttons. Which money '
      + 'controls stay on a phone is M7b.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/payment-runs/1/': () => PAYMENT_RUN },
    render: () => <Console path="/admin/payments/1" params={{ id: '1' }}><PaymentRunPage /></Console>,
  },
  {
    slug: 'm7-student',
    title: 'Admin — student detail',
    note: 'Mobile M7a: ten cards become sections; the danger zone keeps its coloured box.',
    routes: { ...SCOPES, '/api/v1/admin/students/u-1/': () => STUDENT },
    render: () => <Console path="/admin/students/u-1" role={SUPER} params={{ id: 'u-1' }}><StudentDetailPage /></Console>,
  },
  {
    slug: 'm7-org-settings',
    title: 'Admin — organisation settings',
    note: 'Mobile M7a: the underlined tab bar is four 44 px chips on a phone (it ran off the edge).',
    routes: { ...SCOPES },
    render: () => <Console path="/admin/organisation/settings"><OrgSettingsPage /></Console>,
  },
  {
    slug: 'm7-request',
    title: 'Admin — a request',
    note: 'Mobile M7a (layout only): sections, 44 px actions.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/requests/7/': () => REQUEST },
    render: () => <Console path="/admin/requests/7" params={{ id: '7' }}><RequestDetailPage /></Console>,
  },
  {
    slug: 'm7-requests',
    title: 'Admin — the Requests list',
    note: 'Mobile M7a (light): the rows divided, not boxed.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/requests/': () => ({
      count: 3, total_pages: 1, page: 1, page_size: 25, ids: [7, 8, 9],
      summary: { action: 1, progress: 1, closed: 1, all: 3 },
      requests: [requestRow(7, 'Tambah laporan bulanan untuk penaja', 'quoted', ['answer_needed']),
        requestRow(8, 'Betulkan ejaan pada surat tawaran', 'in_progress'), requestRow(9, 'Eksport senarai pelajar', 'done')],
    }) },
    render: () => <Console path="/admin/requests"><RequestsPage /></Console>,
  },
  {
    slug: 'm7b-desktop-only',
    title: 'Admin — a desktop-only page on a phone (Contract templates)',
    note: 'Mobile M7b (owner): below md the shared panel REPLACES the page — why, and one 44 px way back; from md the '
      + 'page as it was.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/contracts/': () => ({ templates: [] }) },
    render: () => <Console path="/admin/contracts" role={SUPER}><ContractsPage /></Console>,
  },
  {
    slug: 'm7b-desktop-only-editor',
    title: 'Admin — a desktop-only editor on a phone (one contract template)',
    note: 'Mobile M7b: a dynamic desktop-only route (contracts/[id]) gets the same panel with its own reason.',
    routes: { ...SCOPES },
    render: () => <Console path="/admin/contracts/1" role={SUPER} params={{ id: '1' }}><ContractEditorPage /></Console>,
  },
]
