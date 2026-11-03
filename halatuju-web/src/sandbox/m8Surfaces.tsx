'use client'

/**
 * Mobile M8, mounted for mobile-check and the owner's phone review: the last student and sponsor "Must" screens a
 * stranger cannot open — the award quiz and the signed award, the scholarship onboarding steps, the sponsor 404,
 * the sponsor's set-a-new-password page, the terms read back, the trust page, the STPM quiz and the e-mail check.
 * Each is the REAL page with fixtures.
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and `mobile-check/targets.ts`
 * reads this file's list too. Identity is synthetic: a hand-filled `AuthContext` (never `AuthProvider`, which would
 * mint a real anonymous user) or the sponsor portal's own context values (`sponsorM5Surfaces.tsx`). The network is
 * the sandbox's stub (`stubFetch.ts`); every endpoint these pages read is answered here, with invented people.
 *
 * ⚠ THE RESET PAGE is the one screen whose form appears only when the sponsor's Supabase client holds a session (the
 * recovery link opens one). It never asks our API, so there is nothing to stub: a SYNTHETIC session — a made-up
 * token, a made-up user, ten minutes to run — is written under the sponsor client's storage key before the page
 * mounts, and the client reads it back with no network call (it only refreshes near expiry). Local sandbox only:
 * the sandbox is compiled out of every normal build. Nothing is sent — the check aborts every Supabase auth call.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { SearchParamsContext } from 'next/dist/shared/lib/hooks-client-context.shared-runtime'
import ScholarshipAwardPage from '@/app/scholarship/award/page'
import ScholarshipOnboardingPage from '@/app/scholarship/onboarding/page'
import SponsorNotFound from '@/app/sponsor/not-found'
import SponsorResetPasswordPage from '@/app/sponsor/auth/reset/page'
import SponsorTermsPage from '@/app/sponsor/(portal)/terms/page'
import TrustPage from '@/app/sponsor/(portal)/trust/page'
import StpmQuizPage from '@/app/stpm/quiz/page'
import VerifyEmailPage from '@/app/verify-email/page'
import { AuthContext } from '@/lib/auth-context'
import { SPONSOR_STORAGE_KEY } from '@/lib/sponsor-supabase'
import { KEY_STPM_GRADES } from '@/lib/storage'
import { sandboxApplication } from './fixtures/scholarship'
import { Portal, SPONSOR_ROUTES, TERMS, TapOnce } from './sponsorM5Surfaces'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

const TOKEN = 'sandbox-not-a-real-token'

/** A signed-in student, synthetic. `store` is written to localStorage before the page mounts. */
function SignedIn({ store, children }: { store?: Record<string, string>; children: ReactNode }) {
  useState(() => {
    try {
      for (const [k, v] of Object.entries(store ?? {})) localStorage.setItem(k, v)
    } catch { /* storage blocked: the page shows its empty state */ }
    return null
  })
  return (
    <AuthContext.Provider value={{
      status: 'ready', isAuthenticated: true, isAnonymous: false, hasSession: true, isLoading: false, token: TOKEN,
      showAuthGate: () => {}, refreshProfile: async () => {}, profile: { results_held: 'spm' },
      session: { user: { id: 'sandbox-student-not-a-real-id', email: 'pelajar@contoh.invalid' } },
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

/** Taps each selector in turn, once the page has drawn it (walks a wizard to a later step) — design review only. */
function TapInTurn({ selectors }: { selectors: string[] }) {
  const [at, setAt] = useState(0)
  useEffect(() => {
    if (at >= selectors.length) return
    const id = window.setInterval(() => {
      const el = document.querySelector<HTMLElement>(selectors[at])
      if (el) { el.click(); window.clearInterval(id); setAt((n) => n + 1) }
    }, 150)
    return () => window.clearInterval(id)
  }, [at, selectors])
  return null
}

// ── The award: the comprehension quiz, and the agreement once signed ────────────────────────────

const OFFER = { amount: '6000.00', accept_deadline: '2026-12-15T00:00:00Z' }
const PREVIEW = {
  award_amount: '6000.00', payment_schedule: 'RM 500 sebulan, 12 bulan', institution_name: 'Politeknik Teladan Johor',
  course_name: 'Diploma Kejuruteraan Elektrik', progress_standard: '', foundation_signatory_name: 'Pengerusi',
  foundation_signatory_title: 'Yayasan Contoh', rendered_html: '<p>Sample agreement for the design sandbox.</p>',
}
/** Two checkpoints, the first in long Tamil (the server serves the student's language). */
const COMPREHENSION = {
  template_version: '2026.1', locale_used: 'ta',
  checkpoints: [
    { tag: 'பிரிவு 2 · உதவித்தொகை எவ்வாறு வழங்கப்படுகிறது',
      plain: 'அறக்கட்டளை ஒவ்வொரு மாதமும் உங்கள் பயிற்சி நிறுவனத்தில் நீங்கள் சேர்ந்திருப்பதை உறுதிசெய்த பின்னரே பணத்தை வழங்கும்.',
      question: 'நீங்கள் படிப்பை நிறுத்தினால் அல்லது பாடத்திட்டத்தை மாற்றினால் என்ன செய்ய வேண்டும்?',
      options: ['ஒன்றும் செய்ய வேண்டியதில்லை; அடுத்த ஆண்டு சொன்னால் போதும்',
        'பதினான்கு நாட்களுக்குள் அறக்கட்டளைக்குத் தெரிவிக்க வேண்டும்',
        'என் பெற்றோர் மட்டும் பள்ளிக்குத் தெரிவித்தால் போதும்'],
      correct: 1, why: 'ஒப்பந்தத்தின் 3.1 ஆம் பிரிவு இதைக் கேட்கிறது, அதனால் உதவித்தொகை சரியான மாணவருக்குச் செல்லும்.' },
    { tag: 'Bahagian 4 · Penjamin', plain: 'Ibu bapa atau penjaga anda menandatangani sebagai penjamin.',
      question: 'Siapakah penjamin anda?', options: ['Rakan sekelas', 'Ibu bapa atau penjaga', 'Pensyarah'],
      correct: 1, why: 'Penjamin ialah ibu bapa atau penjaga yang menandatangani bersama anda.' },
  ],
}
const awardRoutes = (body: object) => ({
  '/api/v1/scholarship/award/': () => ({ offer: OFFER, finalising: false, acceptance_enabled: true, is_minor: false, ...body }),
  '/api/v1/scholarship/award/comprehension-quiz/': () => COMPREHENSION,
})
const SIGNED = {
  id: 9, status: 'signed', version: '2026.1', locale: 'ta', award_amount: '6000.00', payment_schedule: PREVIEW.payment_schedule,
  institution_name: PREVIEW.institution_name, course_name: PREVIEW.course_name, progress_standard: '',
  foundation_signatory_name: 'Pengerusi', pdf_url: 'https://contoh.invalid/perjanjian-contoh.pdf',
}

// ── Scholarship onboarding: her awarded application ─────────────────────────────────────────────

const AWARDED = { ...sandboxApplication, status: 'awarded' }
const ONBOARDING_ROUTES = {
  '/api/v1/scholarship/applications/': () => ({ total_count: 1, applications: [AWARDED] }),
  [`/api/v1/scholarship/applications/${AWARDED.id}/onboarding-complete/`]: () => AWARDED,
}
const ONBOARDING_NEXT = 'main main button.btn-primary'

// ── Sponsor: the terms read back, the trust page, the reset form ────────────────────────────────

const TERMS_ACCEPTED_ROUTES = {
  ...SPONSOR_ROUTES,
  '/api/v1/sponsor/terms/': () => ({
    terms: TERMS, state: { terms_version: '2026.1', terms_accepted: true, needs_terms: false, terms_basis: 'accepted' },
    signed_name: 'திருமதி கலைச்செல்வி இராமலிங்கம்', accepted_at: '2026-03-01T09:30:00Z' }),
}

const TRUST = {
  legal_entity: 'Yayasan Contoh Berhad (1234567-X)', contact_email: 'amanah@contoh.invalid',
  trustees: [
    { name: 'டத்தோ முத்துக்குமாரசாமி பாலசுப்பிரமணியம்', role: 'Pengerusi Lembaga Pemegang Amanah' },
    { name: 'Puan Contoh Bendahari', role: 'Bendahari' },
  ],
  sources: [{ label: 'Penaja individu', amount: '120000' }, { label: 'Syarikat', amount: '85000' }],
  uses: [{ label: 'Anugerah pelajar', amount: '180000' }, { label: 'Pentadbiran', amount: '12500' }],
  assurance: { fy: '2025', students_verified: 163, disbursed: '1180000', auditor: 'Juruaudit Contoh & Rakan',
    report_url: 'https://contoh.invalid/laporan-2025.pdf' },
  figures_are_illustrative: true, community: { sponsors: 41, students_supported: 63, students_waiting: 12 },
}

/** A synthetic recovery session under the sponsor client's key — see the header. Written during render, before the
 *  page's effect builds the client and reads it. */
function RecoverySession({ children }: { children: ReactNode }) {
  useState(() => {
    try {
      const now = Math.floor(Date.now() / 1000)
      localStorage.setItem(SPONSOR_STORAGE_KEY, JSON.stringify({
        access_token: TOKEN, refresh_token: 'sandbox-not-a-real-refresh', token_type: 'bearer',
        expires_in: 600, expires_at: now + 600,
        user: { id: 'sandbox-sponsor-not-a-real-id', aud: 'authenticated', role: 'authenticated',
          email: 'penaja.contoh@contoh.invalid', app_metadata: {}, user_metadata: {}, created_at: '2026-01-01T00:00:00Z' },
      }))
    } catch { /* storage blocked: the page shows "this link has expired" */ }
    return null
  })
  return <>{children}</>
}

// ── The STPM quiz: two questions, the first four tiles in long Tamil ────────────────────────────

const STPM_GRADES = JSON.stringify({ PA: 'A', MATH_T: 'A-', PHYSICS: 'B+', CHEMISTRY: 'B', BIOLOGY: 'A' })
const sq = (text: string, icon: string, field?: string) => ({ text, icon, signals: field ? { [field]: 1 } : {} })
const STPM_QUIZ = {
  branch: 'science', riasec_seed: {}, primary_seed: [], has_cross_stream: false, q3_variants: {},
  questions: [
    { id: 'q1', prompt: 'எந்த வகையான வேலை உங்களுக்கு மிகவும் பிடிக்கும்?', options: [
      sq('ஆய்வகத்தில் சோதனைகள் செய்வது', 'microscope'), sq('நோயாளிகளைப் பராமரித்து உதவுவது', 'stethoscope'),
      sq('இயந்திரங்களை வடிவமைத்துக் கட்டுவது', 'gear'), sq('கணினி நிரல்களை எழுதுவது', 'computer')] },
    { id: 'q2', prompt: 'Which field pulls you most?', options: [
      sq('Medicine and health sciences', 'stethoscope', 'field_health'),
      sq('Engineering and technology', 'gear', 'field_engineering'),
      sq('Pure sciences and research', 'test_tube', 'field_science')] },
  ],
  q5: { id: 'q5', prompt: 'How do you like to learn?', options: [
    sq('By doing', 'hands_tools'), sq('By reading', 'books'), sq('With others', 'people_bubbles')] },
  trunk_remaining: [],
}

// ── The e-mail check (a link from the profile's "verify your e-mail") ───────────────────────────

const VERIFY_TOKEN = 'sandbox-verify-token'
const WITH_TOKEN = new URLSearchParams(`token=${VERIFY_TOKEN}`)
const NO_TOKEN = new URLSearchParams()

export const LAST_MUST_SURFACES: Surface[] = [
  {
    slug: 'award-quiz',
    title: 'Award — the comprehension quiz (start)',
    note: 'Mobile M8: before she signs, the "Understand" step — what happens next and the 44 px Begin.',
    routes: awardRoutes({ bursary_preview: { ...PREVIEW, comprehension_passed: false, guarantor_phone_verified: false } }),
    render: () => <SignedIn><ScholarshipAwardPage /></SignedIn>,
  },
  {
    slug: 'award-quiz-question',
    title: 'Award — a quiz checkpoint (long Tamil)',
    note: 'Mobile M8: the first checkpoint, in Tamil: what it means, the question and three full-width answers.',
    routes: awardRoutes({ bursary_preview: { ...PREVIEW, comprehension_passed: false, guarantor_phone_verified: false } }),
    render: () => (
      <SignedIn><ScholarshipAwardPage /><TapOnce selector="main main button.w-full" /></SignedIn>
    ),
  },
  {
    slug: 'award-signed',
    title: 'Award — signed (download the agreement)',
    note: 'Mobile M8: the agreement is signed — the download and the way back to her application, both 44 px.',
    routes: awardRoutes({ bursary_agreement: SIGNED }),
    render: () => <SignedIn><ScholarshipAwardPage /></SignedIn>,
  },
  {
    slug: 'scholarship-onboarding-welcome',
    title: 'Scholarship onboarding — welcome',
    note: 'Mobile M8: after the award, the four-step line and three things to know, as the page itself on a phone.',
    routes: ONBOARDING_ROUTES,
    render: () => <SignedIn><ScholarshipOnboardingPage /></SignedIn>,
  },
  {
    slug: 'scholarship-onboarding-questions',
    title: 'Scholarship onboarding — three questions',
    note: 'Mobile M8: a 16 px text box and two pairs of 44 px choices; Continue and Back.',
    routes: ONBOARDING_ROUTES,
    render: () => (
      <SignedIn><ScholarshipOnboardingPage /><TapInTurn selectors={[ONBOARDING_NEXT]} /></SignedIn>
    ),
  },
  {
    slug: 'scholarship-onboarding-done',
    title: 'Scholarship onboarding — done',
    note: 'Mobile M8: the answers saved (the stub accepts and discards them); what happens next and the way back.',
    routes: ONBOARDING_ROUTES,
    render: () => (
      <SignedIn><ScholarshipOnboardingPage /><TapInTurn selectors={[ONBOARDING_NEXT, ONBOARDING_NEXT]} /></SignedIn>
    ),
  },
  {
    slug: 'sponsor-not-found',
    title: 'Sponsor — the portal 404',
    note: 'Mobile M8: a mistyped /sponsor/… address — the portal\'s own 404 and one 44 px way back to the portal.',
    render: () => <SponsorNotFound />,
  },
  {
    slug: 'sponsor-reset',
    title: 'Sponsor — set a new password',
    note: 'Mobile M8: where the reset e-mail lands — the rules, two 48 px password fields and Save. The recovery '
      + 'session is synthetic (see the file header).',
    render: () => <RecoverySession><SponsorResetPasswordPage /></RecoverySession>,
  },
  {
    slug: 'sponsor-terms-read',
    title: 'Sponsor — the terms, read back',
    note: 'Mobile M8: the terms she accepted, her signed name in Tamil and when; the sections in full.',
    routes: TERMS_ACCEPTED_ROUTES,
    render: () => <Portal path="/sponsor/account"><SponsorTermsPage /></Portal>,
  },
  {
    slug: 'sponsor-trust',
    title: 'Sponsor — trust and transparency',
    note: 'Mobile M8: who we are, two trustees (one long Tamil name), sources and uses, and the assurance figures.',
    routes: SPONSOR_ROUTES,
    render: () => <Portal path="/sponsor/account" portal={{ trust: TRUST }}><TrustPage /></Portal>,
  },
  {
    slug: 'stpm-quiz',
    title: 'STPM quiz — four tiles (long Tamil)',
    note: 'Mobile M8: the STPM interest quiz\'s first question — four square tiles in Tamil, Next and Previous.',
    routes: { '/api/v1/stpm/quiz/questions/': () => STPM_QUIZ },
    render: () => <SignedIn store={{ [KEY_STPM_GRADES]: STPM_GRADES }}><StpmQuizPage /></SignedIn>,
  },
  {
    slug: 'stpm-quiz-list',
    title: 'STPM quiz — three answers as rows',
    note: 'Mobile M8: the second question (the first is answered, the page moves on by itself) — three answers '
      + 'drawn as full-width rows.',
    routes: { '/api/v1/stpm/quiz/questions/': () => STPM_QUIZ },
    render: () => (
      <SignedIn store={{ [KEY_STPM_GRADES]: STPM_GRADES }}>
        <StpmQuizPage /><TapOnce selector="main main .grid button" />
      </SignedIn>
    ),
  },
  {
    slug: 'verify-email-done',
    title: 'Verify e-mail — confirmed',
    note: 'Mobile M8: the link in the verification e-mail worked; one 44 px way to the profile.',
    routes: { [`/api/v1/profile/verify-email/${VERIFY_TOKEN}/`]: () => ({ email: 'pelajar@contoh.invalid' }) },
    render: () => <SearchParamsContext.Provider value={WITH_TOKEN}><VerifyEmailPage /></SearchParamsContext.Provider>,
  },
  {
    slug: 'verify-email-failed',
    title: 'Verify e-mail — the link is broken',
    note: 'Mobile M8: a link with no token — the failure and the same way to the profile.',
    render: () => <SearchParamsContext.Provider value={NO_TOKEN}><VerifyEmailPage /></SearchParamsContext.Provider>,
  },
]
