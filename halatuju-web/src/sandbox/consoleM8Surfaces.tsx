'use client'

/**
 * Mobile M8 phase B2, mounted for mobile-check and the owner's phone review: the last console "Must" screens a
 * stranger cannot open — the console's 404, a mentor's My students and one student, the Organisation overview, the
 * common Profile (a reviewer and an organisation admin), the Programme Overview (a reviewer and an organisation
 * admin) and the set-a-password page an invite or reset e-mail lands on. Each is the REAL page, inside the REAL
 * console shell where it has one, with invented fixtures and long Tamil names.
 *
 * ⚠ IDENTITY IS SYNTHETIC: an `AdminAuthContext` value — never `AdminAuthProvider`, never a sign-in — as in
 * `adminM7Surfaces.tsx`. The network is the sandbox's stub (`stubFetch.ts`): a write is accepted and discarded.
 *
 * ⚠ THE SET-PASSWORD PAGE is the one screen whose form appears only when the admin Supabase client holds a session
 * (the e-mail link opens one). It never asks our API to draw, so there is nothing to stub: a SYNTHETIC session — a
 * made-up token, a made-up user, ten minutes to run — is written under the admin client's storage key before the
 * page mounts (`sponsor-reset` in `m8Surfaces.tsx` does the same for the sponsor client). Local sandbox only: the
 * sandbox is compiled out of every normal build, and the check aborts every Supabase auth call. Nothing is sent.
 *
 * Spread into `LAST_MUST_SURFACES` (so `surfaces.tsx`, on the oversize ledger, is not touched);
 * `mobile-check/targets.ts` reads this file's list too.
 */
import { useState, type ReactNode } from 'react'
import { PathParamsContext } from 'next/dist/shared/lib/hooks-client-context.shared-runtime'
import { AppShell } from '@/components/admin/AppShell'
import { AdminAuthContext } from '@/lib/admin-auth-context'
import { ADMIN_STORAGE_KEY } from '@/lib/admin-supabase'
import AdminNotFound from '@/app/admin/not-found'
import MyStudentsPage from '@/app/admin/my-students/page'
import MyStudentPage from '@/app/admin/my-students/[id]/page'
import OrganisationOverviewPage from '@/app/admin/organisation/page'
import AdminProfilePage from '@/app/admin/profile/page'
import ProgrammeOverviewPage from '@/app/admin/programme/overview/page'
import ReviewerDetailPage from '@/app/admin/organisation/reviewers/[id]/page'
import AdminSetPasswordPage from '@/app/admin/set-password/page'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

const TOKEN = 'sandbox-not-a-real-token'
const LONG_TAMIL = 'திருமதி கலைச்செல்வி இராமலிங்கம் சுப்பிரமணியம்'

const ORG_ADMIN = {
  is_admin: true, is_super_admin: false, role: 'org_admin', admin_id: 1,
  org_name: 'Yayasan Contoh', owning_org_id: 1, owning_org_name: 'Yayasan Pendidikan Contoh Malaysia Berhad',
  admin_name: 'Pentadbir Contoh', reviewer_profile_complete: true,
  permissions: ['review', 'qc', 'see_all', 'payments', 'spending', 'sponsors'],
}
const REVIEWER = {
  ...ORG_ADMIN, role: 'reviewer', admin_id: 7, admin_name: LONG_TAMIL, permissions: ['review'],
}
const MENTOR = {
  ...ORG_ADMIN, role: 'mentor', admin_id: 9, admin_name: 'முத்துக்குமாரசாமி பாலசுப்பிரமணியம்', permissions: [],
}

const SCOPES: Record<string, () => unknown> = {
  '/api/v1/admin/scholarship/scopes/': () => ({
    organisations: [{ id: 1, code: 'contoh', name: 'Yayasan Contoh' }],
    programmes: [{ id: 1, code: 'contoh-2026', name: 'Biasiswa Contoh 2026', organisation_id: 1, is_active: true }],
  }),
}

function Console({ path, role, params, children }: {
  path: string; role: Record<string, unknown>; params?: Record<string, string>; children: ReactNode
}) {
  const inner = (
    <AdminAuthContext.Provider value={{
      session: null, token: TOKEN, isLoading: false, isAdminAuthenticated: true, role: role as never,
      refreshRole: async () => {}, photoUrl: null, setPhotoUrl: () => {},
    } as never}>
      <AppShell path={path}>{children}</AppShell>
    </AdminAuthContext.Provider>
  )
  return params ? <PathParamsContext.Provider value={params}>{inner}</PathParamsContext.Provider> : inner
}

// ── A mentor's students ─────────────────────────────────────────────────────────────────────────

const help = (university: boolean, scholarship: boolean) => ({ university, scholarship, flagged: false })
const mentee = (id: number, name: string, extra: Record<string, unknown> = {}) => ({
  id, name, course: 'Ijazah Sarjana Muda Kejuruteraan Mekanikal dengan Kepujian',
  institution: 'Universiti Teknologi Malaysia', email: `pelajar${id}@contoh.invalid`, phone: '012-345 6789',
  since: '2026-03-01', meetings: 3, last_meeting: '2026-10-20', latest_result: { cgpa: '3.42', semester: 'Semester 2 2025/26' },
  standing: 'performing', asked_for_help: help(true, false), ...extra,
})
const MY_STUDENTS = {
  organisation: 'Yayasan Contoh',
  students: [
    mentee(1, 'கவிதா த/பெ முனியாண்டி இராஜேந்திரன்', { asked_for_help: help(true, true) }),
    mentee(2, 'Muhammad Haziq bin Contoh', { meetings: 0, last_meeting: null, latest_result: null, standing: 'no_result_yet' }),
    mentee(3, 'Tan Contoh Ling', { standing: 'underperforming', latest_result: { cgpa: '2.31', semester: 'Semester 1 2025/26' } }),
  ],
}
const MY_STUDENT = {
  ...mentee(1, 'கவிதா த/பெ முனியாண்டி இராஜேந்திரன்', { asked_for_help: help(true, true) }),
  organisation: 'Yayasan Contoh',
  meetings: [
    { id: 1, met_on: '2026-10-20', mode: 'phone', by_you: true, minutes: 30,
      notes: 'அவள் இந்தச் செமஸ்டரில் இயந்திரவியல் பாடத்தில் சிரமப்படுகிறாள்; வாரம் இருமுறை படிப்புக் குழுவில் சேர ஒப்புக்கொண்டாள்.',
      next_step: 'Semak keputusan ujian pertengahan semester', concern: true },
    { id: 2, met_on: '2026-09-02', mode: 'in_person', by_you: false },
  ],
}

// ── The Organisation overview ───────────────────────────────────────────────────────────────────

const staff = (id: number, name: string, role: string) => ({
  id, name, email: `staf${id}@contoh.invalid`, is_super_admin: false, role, is_active: true, org_name: 'Yayasan Contoh',
  owning_org_id: 1, owning_org_name: 'Yayasan Contoh', created_at: '2026-01-10T00:00:00Z',
})
const gift = (id: number, code: string, name: string, lifecycle: string, extra: Record<string, unknown> = {}) => ({
  id, code, name_en: name, name_ms: name, name_ta: name, is_active: lifecycle === 'active', apply_copy: {},
  apply_copy_sensitive: [], lifecycle, intake_years: 2, applications: 128, awarded: 42, open_year: 2026,
  delete_blocked_by: 'has_applications', delete_blocked_count: 128, apply_url: `https://contoh.invalid/apply/${code}`, ...extra,
})
const ORG_ROUTES: Record<string, () => unknown> = {
  ...SCOPES,
  '/api/v1/admin/admins/': () => ({ admins: [staff(1, 'Pentadbir Contoh', 'org_admin'), staff(7, LONG_TAMIL, 'reviewer'),
    staff(8, 'Devi Penyemak', 'reviewer'), staff(9, 'Balan Kewangan', 'finance')] }),
  '/api/v1/admin/sponsors/pending-count/': () => ({ count: 2 }),
  '/api/v1/admin/invitations/': () => ({ kind: 'admins', invitations: [], waiting: { admins: 1, sponsors: 3, mentors: 0, sources: 0 },
    totals: { admins: 12, sponsors: 20, mentors: 2, sources: 1 }, grantable: [] }),
  '/api/v1/admin/scholarship/programmes/': () => ({ programmes: [
    gift(1, 'contoh-2026', 'Biasiswa Contoh 2026', 'active'),
    gift(2, 'contoh-tamil', 'உயர்கல்வி உதவித்தொகை — தமிழ்ப் பள்ளி மாணவர்களுக்கான சிறப்புத் திட்டம்', 'draft',
      { applications: 0, awarded: 0, open_year: null, delete_blocked_by: null, delete_blocked_count: 0, intake_years: 0 }),
  ] }),
}

// ── The common Profile ──────────────────────────────────────────────────────────────────────────

const me = (role: Record<string, unknown>, extra: Record<string, unknown> = {}) => ({
  id: role.admin_id, name: role.admin_name, email: 'staf.contoh@contoh.invalid', role: role.role, is_super: false,
  organisation: { id: 1, name: 'Yayasan Contoh' }, source: null, referral_partner: null,
  programmes: [{ id: 1, code: 'contoh-2026', name: 'Biasiswa Contoh 2026' }], permissions: role.permissions,
  first_seen_at: '2026-02-01T08:00:00Z', last_seen_at: '2026-11-03T08:00:00Z',
  job_title: 'தன்னார்வ மதிப்பாய்வாளர், உயர்கல்வி உதவித்தொகைக் குழு',
  about: 'நான் இருபது ஆண்டுகளாகக் கணக்காய்வாளராகப் பணியாற்றுகிறேன்; மாணவர்களின் விண்ணப்பங்களைப் படிப்பதில் மகிழ்ச்சி.',
  phone: '123456789', share_phone_with_team: true, share_phone_with_students: false, photo_url: null, ...extra,
})
const REVIEWER_PROFILE = {
  highest_qualification: "Bachelor's Degree", university: 'Universiti Malaya', graduation_year: 2004,
  field_of_study: 'Perakaunan dan Kewangan', phone: '123456789', address: '', street_address: '12, Jalan Contoh 3, Taman Contoh',
  postcode: '43000', city: 'Kajang', state: 'Selangor', english_fluency: 'fluent', bm_fluency: 'fluent',
  tamil_fluency: 'fluent', other_language: '', other_language_fluency: '', share_phone_with_students: false,
  paused: false, paused_at: null,
}
const activity = (id: number, verb: string, kind: string, label: string | null) => ({
  id, verb, kind, created_at: `2026-11-0${id}T08:00:00Z`, backfilled: false, meta: {},
  subject: label ? { type: 'application', state: 'visible', label, id } : null,
})
const ACTIVITY = { next: null, results: [
  activity(3, 'verdict_recorded', 'students', 'கவிதா த/பெ முனியாண்டி இராஜேந்திரன்'),
  activity(2, 'interview_submitted', 'students', 'Muhammad Haziq bin Contoh'),
  activity(1, 'profile_updated', 'profile', null),
] }
const profileRoutes = (role: Record<string, unknown>) => ({
  ...SCOPES,
  '/api/v1/admin/me/': () => me(role),
  '/api/v1/admin/me/activity/': () => ACTIVITY,
  '/api/v1/admin/reviewer-profile/': () => REVIEWER_PROFILE,
})

// ── The Programme Overview ──────────────────────────────────────────────────────────────────────

const STATUSES = ['shortlisted', 'submitted', 'profile_complete', 'interviewing', 'interviewed', 'qc_review',
  'awarded', 'active', 'maintenance', 'declined']
const FUNNEL = { total: 128, by_status: Object.fromEntries(STATUSES.map((s, i) => [s, 18 - i])) }
const weeks = ['2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05', '2026-10-12']
const months = ['2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
const APPLICATIONS_SERIES = {
  applications_per_week: weeks.map((week, i) => ({ week, count: 4 + i * 3 })),
  awards_per_month: months.map((month, i) => ({ month, count: i * 2 })),
}
const myCase = (id: number, name: string, band: string) => ({
  id, ref: `HT-2026-00${id}`, applicant_name: name, status: 'interviewing', assigned_at: '2026-10-20T00:00:00Z',
  due_at: '2026-11-10T00:00:00Z', band,
})
const MINE = { open: 3, due_soon: 1, overdue: 1, pace: { completed: 14, turnaround_days: 9 }, cases: [
  myCase(1, 'கவிதா த/பெ முனியாண்டி இராஜேந்திரன்', 'overdue'), myCase(2, 'Muhammad Haziq bin Contoh', 'due_soon'),
  myCase(3, 'Tan Contoh Ling', 'open')] }
const QC = { awaiting: 2, oldest_waiting_days: 4, pace: { completed: 30, turnaround_days: 3 }, cases: [
  { id: 4, ref: 'HT-2026-004', applicant_name: 'Nurul Aina binti Contoh', status: 'qc_review', since: '2026-10-30T00:00:00Z', waiting_days: 4 }] }
const money = (a: number) => String(a.toFixed(2))
const MONEY_SERIES = {
  money_per_month: months.map((month, i) => ({ month, released: money(8000 + i * 500), spent: money(6000 + i * 700),
    released_cum: money(8000 * (i + 1)), spent_cum: money(6000 * (i + 1)), gap: money(2000 - i * 200) })),
  per_student_per_week: weeks.map((week, i) => ({ week, students: 40 + i, spent: money(3200 + i * 90), transactions: 210 + i * 4,
    spent_per_transaction: '15.20', transactions_per_student: '5.1' })),
  per_student_overall: { students: 42, weeks: 6, spent: '20140.00', transactions: 1320, spent_per_transaction: '15.26',
    weekly_transactions_per_student: '5.2' },
  by_category: [{ code: 'food', total: '9800.00', transactions: 700 }, { code: 'transport', total: '4200.00', transactions: 300 },
    { code: 'study', total: '3600.00', transactions: 120 }, { code: 'hostel', total: '2540.00', transactions: 10 }],
}
const INTAKES = [{ id: 1, code: 'contoh-2026-r1', name: 'Pengambilan 2026', year: 2026, state: 'open' },
  { id: 2, code: 'contoh-2025-r1', name: 'Pengambilan 2025', year: 2025, state: 'finished' }]
const overview = (sections: string[], extra: Record<string, unknown> = {}) => ({
  programme: { code: 'contoh-2026', name: 'Biasiswa Contoh 2026' }, generated_at: '2026-11-04T00:00:00Z',
  data_to: '2026-10-31', sections, intake: null, intakes: INTAKES, funnel: FUNNEL, mine: MINE,
  applications_series: APPLICATIONS_SERIES, ...extra,
})
const OVERVIEW_REVIEWER = overview(['mine', 'funnel', 'applications_series'])
const OVERVIEW_ORG_ADMIN = overview(['attention', 'money', 'funnel', 'applications_series', 'money_series', 'qc'], {
  money: { students: 42, committed: '504000.00', paid: '201600.00', remaining: '302400.00', spent: '180250.50' },
  attention: { unassigned: 4, with_reviewer: 12, due_soon: 3, overdue: 1, awaiting_qc: 2 },
  money_series: MONEY_SERIES, qc: QC,
  layout: ['funnel', 'money', 'attention', 'applications_series', 'money_series'].map((key) => ({ key, on: true })),
  layout_source: 'organisation',
})

/** A synthetic invite session under the ADMIN client's key — see the header. Written during render, before the
 *  page's effect builds the client and reads it. */
function InviteSession({ children }: { children: ReactNode }) {
  useState(() => {
    try {
      const now = Math.floor(Date.now() / 1000)
      localStorage.setItem(ADMIN_STORAGE_KEY, JSON.stringify({
        access_token: TOKEN, refresh_token: 'sandbox-not-a-real-refresh', token_type: 'bearer',
        expires_in: 600, expires_at: now + 600,
        user: { id: 'sandbox-admin-not-a-real-id', aud: 'authenticated', role: 'authenticated',
          email: 'kalaiselvi.ramalingam.penyemak@contoh.invalid', app_metadata: {}, user_metadata: {},
          created_at: '2026-01-01T00:00:00Z' },
      }))
    } catch { /* storage blocked: the page shows "this link has expired" */ }
    return null
  })
  return <>{children}</>
}

// ── One reviewer (Mobile M8 follow-up: the four figures ran 70 px past the card at 360) ─────────────────
const REVIEWER_DETAIL = {
  id: 7, name: LONG_TAMIL, email: 'penyemak7@contoh.invalid', role: 'reviewer', languages: ['ta', 'ms', 'en'],
  open_now: 4, awaiting_review: 12, interviewing: 3, completed: 148, turnaround_days: 12.5, paused: false, paused_at: null,
  is_active: true, last_seen_at: '2026-11-02T09:00:00Z', programme_id: null, programme_name: '',
  programmes: [{ id: 1, code: 'contoh-2026', name: 'Biasiswa Contoh 2026', is_active: true },
    { id: 2, code: 'contoh-stpm', name: 'Bantuan STPM Contoh', is_active: false }],
  recommended: 96, declined: 31, rejected_after_review: 9, awaiting_qc: 12,
  created_at: '2026-01-10T00:00:00Z', qualification: 'degree', university: 'Universiti Malaya', graduation_year: 2004,
  field_of_study: 'Pendidikan', phone: '123456789', share_phone_with_students: true, other_language: '',
  reopens: [{ id: 1, application_id: 412, reason: 'தவறான ஆவணம் பதிவேற்றப்பட்டது; மாணவர் புதிய சான்றிதழை அனுப்பினார்.',
    reopened_by: 'Pentadbir Contoh', at: '2026-10-14T08:00:00Z' }],
  pausable: true,
}

export const CONSOLE_MUST_SURFACES: Surface[] = [
  {
    slug: 'm8-admin-not-found',
    title: 'Admin — the console 404',
    note: 'Mobile M8: a mistyped /admin/… address — the console\'s own 404 inside the shell, one 44 px way back.',
    routes: SCOPES,
    render: () => <Console path="/admin/no-such-page" role={REVIEWER}><AdminNotFound /></Console>,
  },
  {
    slug: 'm8-my-students',
    title: 'Mentor — My students',
    note: 'Mobile M8: a mentor\'s students as rows (one long Tamil name), 44 px Log a meeting and Call.',
    routes: { ...SCOPES, '/api/v1/admin/mentor/students/': () => MY_STUDENTS },
    render: () => <Console path="/admin/my-students" role={MENTOR}><MyStudentsPage /></Console>,
  },
  {
    slug: 'm8-my-student',
    title: 'Mentor — one student',
    note: 'Mobile M8: who she is and how to reach her, the latest result, what she asked for help with and the '
      + 'meetings (the mentor\'s own in full, in Tamil).',
    routes: { ...SCOPES, '/api/v1/admin/mentor/students/1/': () => MY_STUDENT },
    render: () => <Console path="/admin/my-students/1" role={MENTOR} params={{ id: '1' }}><MyStudentPage /></Console>,
  },
  {
    slug: 'm8-organisation',
    title: 'Admin — Organisation overview',
    note: 'Mobile M8: the three counts as rows, the vetting callout and the gift programmes (one long Tamil name).',
    routes: ORG_ROUTES,
    render: () => <Console path="/admin/organisation" role={ORG_ADMIN}><OrganisationOverviewPage /></Console>,
  },
  {
    slug: 'm8-profile-reviewer',
    title: 'Admin — Profile (a reviewer)',
    note: 'Mobile M8: the common profile as a reviewer sees it — you, contact, qualifications, address, taking part, '
      + 'sign-in, My activity; sections, 16 px fields, one Save.',
    routes: profileRoutes(REVIEWER),
    render: () => <Console path="/admin/profile" role={REVIEWER}><AdminProfilePage /></Console>,
  },
  {
    slug: 'm8-profile-org-admin',
    title: 'Admin — Profile (an organisation admin)',
    note: 'Mobile M8: the same page for an organisation admin — your access names the gift and the permissions.',
    routes: profileRoutes(ORG_ADMIN),
    render: () => <Console path="/admin/profile" role={ORG_ADMIN}><AdminProfilePage /></Console>,
  },
  {
    slug: 'm8-overview-reviewer',
    title: 'Admin — Programme Overview (a reviewer)',
    note: 'Mobile M8: a reviewer\'s Overview — my cases with their clocks, the funnel and the applications chart.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/programme-overview/': () => OVERVIEW_REVIEWER },
    render: () => <Console path="/admin/programme/overview" role={REVIEWER}><ProgrammeOverviewPage /></Console>,
  },
  {
    slug: 'm8-overview-org-admin',
    title: 'Admin — Programme Overview (an organisation admin)',
    note: 'Mobile M8: every panel — attention, money, the funnel, both series, QC — and Customise.',
    routes: { ...SCOPES, '/api/v1/admin/scholarship/programme-overview/': () => OVERVIEW_ORG_ADMIN },
    render: () => <Console path="/admin/programme/overview" role={ORG_ADMIN}><ProgrammeOverviewPage /></Console>,
  },
  {
    slug: 'm8-reviewer-detail',
    title: 'Admin — one reviewer',
    note: 'Mobile M8 follow-up: the record of one reviewer, as an organisation admin sees it (a long Tamil name) — the four '
      + 'figures two by two on a phone, the outcomes, about them and a reopened decision.',
    routes: { ...SCOPES, '/api/v1/admin/reviewers/7/': () => REVIEWER_DETAIL },
    render: () => (
      <Console path="/admin/organisation/reviewers/7" role={ORG_ADMIN} params={{ id: '7' }}><ReviewerDetailPage /></Console>
    ),
  },
  {
    slug: 'm8-set-password',
    title: 'Admin — set your password',
    note: 'Mobile M8: where an invite or reset e-mail lands — the account e-mail, two 48 px password fields and Set. '
      + 'The invite session is synthetic (see the file header).',
    render: () => <InviteSession><AdminSetPasswordPage /></InviteSession>,
  },
]
