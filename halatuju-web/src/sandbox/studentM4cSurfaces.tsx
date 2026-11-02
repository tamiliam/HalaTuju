'use client'

/**
 * Mobile M4c, mounted for mobile-check and the owner's phone review: the student pages swept to one box
 * level that a stranger cannot open — My Bursary (overview, News, Surveys), the first two onboarding
 * steps and the interest quiz — each the REAL page with fixtures.
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and
 * `mobile-check/targets.ts` reads this file's list too. Identity is a synthetic `AuthContext` value —
 * never `AuthProvider` (it would mint a real anonymous Supabase user) and never a real sign-in. The
 * network is the sandbox's stub (`stubFetch.ts`); every endpoint these pages read is answered here, with
 * invented people and numbers. A tab the page opens from its address (`?tab=news`) is written into the
 * address DURING render, before the page's own effect reads it.
 */
import { useState, type ReactNode } from 'react'
import BursaryPage from '@/app/scholarship/bursary/page'
import ExamTypePage from '@/app/onboarding/exam-type/page'
import GradesPage from '@/app/onboarding/grades/page'
import QuizPage from '@/app/quiz/page'
import { AuthContext } from '@/lib/auth-context'
import { KEY_EXAM_TYPE, KEY_PROFILE, rememberBursaryFile } from '@/lib/storage'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

/** A signed-in student, synthetic. `tab` puts `?tab=…` in the address for the page to read. */
function SignedIn({ tab, examType, children }: { tab?: string; examType?: string; children: ReactNode }) {
  useState(() => {
    try {
      if (examType) localStorage.setItem(KEY_EXAM_TYPE, examType)
      localStorage.setItem(KEY_PROFILE, JSON.stringify({ gender: 'female', nationality: 'malaysian' }))
    } catch { /* storage blocked: the page shows its empty state */ }
    rememberBursaryFile(true)
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href)
      if (tab) url.searchParams.set('tab', tab); else url.searchParams.delete('tab')
      window.history.replaceState(window.history.state, '', url.toString())
    }
    return null
  })
  return (
    <AuthContext.Provider value={{
      status: 'ready', isAuthenticated: true, isAnonymous: false, hasSession: true, isLoading: false,
      token: 'sandbox-not-a-real-token', showAuthGate: () => {}, refreshProfile: async () => {},
      profile: { results_held: 'spm' },
      session: { user: { email: 'pelajar@contoh.invalid', user_metadata: { full_name: 'Kavitha Raman' } } },
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

const APP = 71

/** `scholarship/bursary/summary/` for an invented funded student with every tab switched on. */
const SUMMARY = {
  application_id: APP, name: 'KAVITHA RAMAN', gift: 'Yayasan Contoh Bursary',
  gift_names: { en: 'Yayasan Contoh Bursary', ms: 'Biasiswa Yayasan Contoh', ta: 'Yayasan Contoh உதவித்தொகை' },
  course: 'Diploma Kejuruteraan Mekanikal', institution: 'Politeknik Ungku Omar',
  status: 'maintenance', closure_reason: '', in_maintenance: true, can_record_results: true, support_paused: false,
  funds: { award_amount: '6000.00', received: '2500.00', remaining: '3500.00',
    last_payment: { amount: '500.00', at: '2026-10-15' } },
  latest_result: { semester: 'Semester 2', cgpa: '3.42', at: '2026-09-30', review_status: 'accepted' },
  next_result_due: '2027-03-31', next_result_overdue: false,
  has_letters: true, letters_to_acknowledge: 1, mentoring_tab: true,
  news_tab: true, news_unread: 2, surveys_tab: true, surveys_to_answer: 1,
}

const FUNDS = {
  closed: false, award_amount: '6000.00', received: '2500.00', remaining: '3500.00',
  releases: [{ amount: '500.00', released_on: '2026-10-15' }, { amount: '2000.00', released_on: '2026-07-01' }],
  spending: {
    promised: '6000.00', released: '2500.00', spent: '1840.50', left: '659.50', as_at: '2026-10-31',
    categories: [
      { code: 'food', total: '820.00' }, { code: 'transport', total: '410.50' },
      { code: 'study', total: '380.00' }, { code: 'phone', total: '230.00' },
    ],
  },
}

const CONTRACT = {
  exists: true, executed_on: '2026-06-20', witnessed: true, pdf_url: null, pdf_expires_in: 0,
  parties: [
    { role: 'student', name: 'Kavitha Raman', signed_on: '2026-06-18' },
    { role: 'guarantor', name: 'Raman a/l Muthu', relationship: 'father', signed_on: '2026-06-18' },
    { role: 'foundation', name: 'S. Letchumi', title: 'Programme lead', signed_on: '2026-06-20' },
  ],
}

const RESULTS = {
  results: [
    { id: 2, semester: 'Semester 2', cgpa: '3.42', graduated: false, results_slip: 12, note: '',
      created_at: '2026-09-30', review_status: 'accepted', review_note: '' },
    { id: 1, semester: 'Semester 1', cgpa: '3.10', graduated: false, results_slip: 11, note: '',
      created_at: '2026-03-30', review_status: 'queried', review_note: 'The slip is cut off at the bottom.' },
  ],
}

const NEWS = {
  organisation: 'Yayasan Contoh',
  announcements: [
    { id: 3, title: 'Semester 2 results: please upload by 31 March', pinned: true, new: true,
      body: 'Upload your results slip on the Results tab. Guide: https://contoh.invalid/panduan.',
      published_at: '2026-10-28', edited_at: null },
    { id: 2, title: 'Mentor meetings in November', pinned: false, new: true,
      body: 'Your mentor will contact you this month to set a time.\nMeetings can be online.',
      published_at: '2026-10-20', edited_at: '2026-10-21' },
    { id: 1, title: 'Welcome to the programme', pinned: false, new: false,
      body: 'We are glad to have you with us.', published_at: '2026-07-01', edited_at: null },
  ],
}

const SURVEYS = {
  organisation: 'Yayasan Contoh',
  surveys: [
    { id: 5, title: 'How is your first semester going?', intro: 'Five short questions. Your answers help us plan support.',
      status: 'open', opens_at: '2026-10-25', closes_at: '2026-11-15', can_answer: true, answered_at: null, updated_at: null,
      answers: {},
      questions: [
        { id: 51, kind: 'rating', text: 'How settled do you feel at your institution?', hint: '1 = not at all, 5 = very', required: true, options: [] },
        { id: 52, kind: 'one', text: 'How do you usually travel to classes?', hint: '', required: true, options: ['Walk', 'Bus', 'Motorcycle', 'Lift from family'] },
        { id: 53, kind: 'many', text: 'What do you spend most on?', hint: 'Pick all that apply', required: false, options: ['Food', 'Transport', 'Books', 'Phone'] },
        { id: 54, kind: 'yes_no', text: 'Have you met your mentor yet?', hint: '', required: true, options: [] },
        { id: 55, kind: 'long', text: 'Anything else you would like us to know?', hint: '', required: false, options: [] },
      ] },
    { id: 4, title: 'Orientation week', intro: '', status: 'closed', opens_at: '2026-07-01', closes_at: '2026-07-14',
      can_answer: false, answered_at: '2026-07-03', updated_at: null,
      answers: { 41: 'Yes', 42: 4 },
      questions: [
        { id: 41, kind: 'yes_no', text: 'Did you attend orientation?', hint: '', required: true, options: [] },
        { id: 42, kind: 'rating', text: 'How useful was it?', hint: '', required: true, options: [] },
      ] },
  ],
}

const BURSARY_ROUTES = {
  '/api/v1/scholarship/bursary/summary/': () => SUMMARY,
  '/api/v1/scholarship/bursary/funds/': () => FUNDS,
  '/api/v1/scholarship/bursary/contract/': () => CONTRACT,
  [`/api/v1/scholarship/applications/${APP}/semester-results/`]: () => RESULTS,
  [`/api/v1/scholarship/applications/${APP}/promotional-consent/`]: () => ({ granted: false, is_minor: false }),
  [`/api/v1/scholarship/applications/${APP}/graduation-message/`]: () => ({ messages: [] }),
  '/api/v1/scholarship/bursary/news/': () => NEWS,
  '/api/v1/scholarship/bursary/news/read/': () => ({ marked: 2, unread: 0 }),
  '/api/v1/scholarship/bursary/surveys/': () => SURVEYS,
}

const opt = (text: string, icon: string) => ({ text, icon, signals: {} })
/** `quiz/questions/` — two invented questions (the page shows the first). */
const QUIZ = {
  questions: [
    { id: 'q1', prompt: 'Which of these sounds most like you?', select_mode: 'multi', max_select: 2, options: [
      opt('Fixing and building things', 'wrench_gears'), opt('Working with computers', 'laptop_code'),
      opt('Helping and caring for people', 'heart_stethoscope'), opt('Drawing and designing', 'paintbrush_ruler'),
      { text: 'Not sure yet', icon: 'question_sparkle', signals: {}, not_sure: true },
    ] },
    { id: 'q2', prompt: 'Where would you rather work?', options: [
      opt('A workshop', 'workshop_garage'), opt('An office', 'desk_monitor'),
      opt('Outdoors', 'trees_sun'), opt('With a team of people', 'building_people'),
    ] },
  ],
}

export const STUDENT_REST_SURFACES: Surface[] = [
  {
    slug: 'bursary-overview',
    title: 'My Bursary — overview',
    note: 'Rule 15 on a phone (Mobile M4c): her greeting, funds, latest result, contract, sharing and thank-you are '
      + 'plain sections on a 16 px gutter, divided by hairlines; the tabs are 44 px. From md, the cards as before.',
    render: () => <SignedIn><BursaryPage /></SignedIn>,
    routes: BURSARY_ROUTES,
  },
  {
    slug: 'bursary-news',
    title: 'My Bursary — News tab',
    note: 'Three announcements, two new (the brand rule on the left), as sections; the address opens the tab.',
    render: () => <SignedIn tab="news"><BursaryPage /></SignedIn>,
    routes: BURSARY_ROUTES,
  },
  {
    slug: 'bursary-surveys',
    title: 'My Bursary — Surveys tab',
    note: 'One open survey with every kind of question (44 px choices, 48 px ratings, 16 px fields) and one closed '
      + 'survey read back. Sections, not cards.',
    render: () => <SignedIn tab="surveys"><BursaryPage /></SignedIn>,
    routes: BURSARY_ROUTES,
  },
  {
    slug: 'onboarding-exam-type',
    title: 'Onboarding — which results do you have?',
    note: 'The first onboarding step: three choices, each a tap-sized card on a 16 px gutter.',
    render: () => <ExamTypePage />,
  },
  {
    slug: 'onboarding-grades',
    title: 'Onboarding — SPM grades',
    note: 'The SPM results step: the core subjects and the stream as sections on a phone; grade pickers and the '
      + 'add-a-subject buttons are 44 px.',
    render: () => <SignedIn examType="spm"><GradesPage /></SignedIn>,
  },
  {
    slug: 'quiz',
    title: 'Interest quiz — first question',
    note: 'The quiz on a phone: 16 px gutter, the 2 x 2 answer tiles, "Not sure yet" and Previous at 44 px.',
    render: () => <SignedIn><QuizPage /></SignedIn>,
    routes: { '/api/v1/quiz/questions/': () => QUIZ },
  },
]
