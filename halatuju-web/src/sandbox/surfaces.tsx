'use client'

/**
 * The list of screens the sandbox offers, and how each one is mounted.
 *
 * ⚠ EVERY ENTRY MOUNTS A REAL COMPONENT. If a surface cannot be mounted without re-implementing
 * part of it, it does not belong here — fix the component so it can be mounted (usually by taking
 * its data as props), or leave the surface out. A hand-written approximation would be worse than
 * nothing: a designer would sign off on a screen that does not exist.
 *
 * `token` is a synthetic string, never a real session. It exists because the components take one;
 * the stubbed fetch ignores it, and there is no backend for it to reach.
 */
import type { ReactNode } from 'react'
import ScholarshipDocuments from '@/components/ScholarshipDocuments'
import ScholarshipNextSteps from '@/components/ScholarshipNextSteps'
import ScholarshipApplyPage from '@/app/scholarship/apply/page'
import SponsorStudentsPage from '@/app/sponsor/(portal)/students/page'
import { AuthContext } from '@/lib/auth-context'
import { SponsorPortalContext } from '@/lib/sponsor-portal-context'
import {
  sandboxApplication, sandboxApplicationLeanProgramme, sandboxNoApplications,
  sandboxProfileFormSix, sandboxProfileSpm, sandboxProfileStpm,
} from './fixtures/scholarship'
import { sandboxPool } from './fixtures/sponsor'

const SANDBOX_TOKEN = 'sandbox-not-a-real-token'

export interface Surface {
  slug: string
  title: string
  /** What a designer is looking at, and which state it is in — states are chosen, not accidental. */
  note: string
  render: () => ReactNode
  /**
   * Endpoint answers for THIS surface only, layered over the shared ones. Needed where two
   * screens want different answers from the same endpoint — see `setSurfaceRoutes`.
   */
  routes?: Record<string, () => unknown>
}

export const SURFACES: Surface[] = [
  {
    slug: 'documents',
    title: 'Documents',
    note:
      'The student’s upload surface, mid-flight: identity card verified, results slip pending, '
      + 'household income evidenced by an approved STR. The remaining cards are still empty.',
    render: () => (
      <ScholarshipDocuments token={SANDBOX_TOKEN} app={sandboxApplication} />
    ),
  },
  {
    slug: 'documents-lean',
    title: 'Documents — a leaner programme',
    note:
      'The SAME student, at an organisation that asks for less: identity card and results slip '
      + 'only, no household means test, and one optional extra. Nothing about this page is coded '
      + 'differently — it is the same component reading a different configuration, which is what '
      + 'Layer 0 buys. Style both: a tenant will land on each.',
    render: () => (
      <ScholarshipDocuments token={SANDBOX_TOKEN} app={sandboxApplicationLeanProgramme} />
    ),
  },
  {
    slug: 'application-steps',
    title: 'Application — the step wizard',
    note:
      'The pre-submit Step-4 wizard on the FULL programme: five steps in the rail, every '
      + 'story question drawn, the Funding step present. Layer 0 Sprint 4 made the questions '
      + 'configuration-driven; this is the baseline to compare the lean surface against.',
    render: () => (
      <ScholarshipNextSteps
        initialApp={{ ...sandboxApplication, status: 'shortlisted' }}
        token={SANDBOX_TOKEN}
      />
    ),
  },
  {
    slug: 'application-steps-lean',
    title: 'Application — the step wizard, leaner programme',
    note:
      'The SAME student at an organisation that switched questions off: the Funding step is '
      + 'gone from the rail (four steps — computed at render, never stored), and “Your story” '
      + 'no longer draws the daily-life or worries questions. Same component reading a '
      + 'different configuration — nothing about this page is coded differently.',
    render: () => (
      <ScholarshipNextSteps
        initialApp={{ ...sandboxApplicationLeanProgramme, status: 'shortlisted' }}
        token={SANDBOX_TOKEN}
      />
    ),
  },
  {
    slug: 'apply-results',
    title: 'Apply — My Results (sat SPM)',
    note:
      'Step 3 of the application form, for a student whose SPM results are on file. The step '
      + 'DISPLAYS results and offers to correct them; it never collects them — the only place '
      + 'they are entered is the course-guide onboarding, which writes the same profile. Click '
      + '“My Results” in the step rail.',
    routes: { '/api/v1/scholarship/applications/': () => sandboxNoApplications },
    render: () => (
      <WithAuth profile={sandboxProfileSpm}>
        <ScholarshipApplyPage />
      </WithAuth>
    ),
  },
  {
    slug: 'apply-results-stpm',
    title: 'Apply — My Results (sat STPM)',
    note:
      'The same step for a student who has sat STPM: the count of A’s is replaced by the PNGK. '
      + 'Same component, same code path — the branch is `exam_type`.',
    routes: { '/api/v1/scholarship/applications/': () => sandboxNoApplications },
    render: () => (
      <WithAuth profile={sandboxProfileStpm}>
        <ScholarshipApplyPage />
      </WithAuth>
    ),
  },
  {
    slug: 'apply-results-form-six',
    title: 'Apply — My Results (Form Six: the defect)',
    note:
      'A Form Six student: ten SPM grades on file, sitting STPM now, so she answered “STPM” at '
      + '“Choose Your Exam” — the exam she is heading FOR. The step looks only where the declared '
      + 'exam points, finds no CGPA, and tells her WE DO NOT HAVE HER RESULTS while they sit in '
      + 'the database. The button it offers goes back to the screen that produced the '
      + 'declaration. One live applicant is in this state. Compare it against the first surface: '
      + 'same student data, one field different.',
    routes: { '/api/v1/scholarship/applications/': () => sandboxNoApplications },
    render: () => (
      <WithAuth profile={sandboxProfileFormSix}>
        <ScholarshipApplyPage />
      </WithAuth>
    ),
  },
  {
    slug: 'sponsor-browse',
    title: 'Sponsor — browse students',
    note:
      'The sponsor’s discovery grid, and the FIRST surface converted onto the theme tokens '
      + '(Layer 1 F1). Five cards chosen to put every conditional state on screen at once: '
      + 'verified against unverified enrolment, artwork against none, fully funded against '
      + 'part-funded against untouched, a written blurb against an empty one, and a reporting '
      + 'date against a missing one. Check it in BOTH modes — this is the surface the sprint '
      + 'claims is correct in dark.',
    render: () => (
      <WithSponsorPortal>
        <SponsorStudentsPage />
      </WithSponsorPortal>
    ),
  },
]

/**
 * The portal pages read their data from a context rather than props, so the sandbox supplies that
 * context with fixtures instead of the network. `SponsorPortalContext` is exported for exactly this
 * — the page below is the REAL one, unmodified.
 *
 * Only the fields this page reads are filled. Casting a partial value is deliberate: filling
 * fourteen unrelated fields with nulls would suggest they are part of what this surface shows.
 */
/**
 * The signed-in student screens read their identity from `useAuth`, so the sandbox supplies that
 * context with a synthetic value. `AuthProvider` is deliberately NOT used: it mints an anonymous
 * Supabase user on mount, and a design review must not create real auth rows.
 *
 * Only the four fields these screens read are filled — `status`, `profile`, `token`, and the auth
 * gate they never open. Casting a partial value is the same deliberate choice made below.
 */
function WithAuth({ profile, children }: { profile: unknown; children: ReactNode }) {
  return (
    <AuthContext.Provider
      value={{ status: 'ready', profile, token: SANDBOX_TOKEN, showAuthGate: () => {} } as never}
    >
      {children}
    </AuthContext.Provider>
  )
}

function WithSponsorPortal({ children }: { children: ReactNode }) {
  return (
    <SponsorPortalContext.Provider value={{ pool: sandboxPool } as never}>
      {children}
    </SponsorPortalContext.Provider>
  )
}

export function surfaceBySlug(slug: string): Surface | undefined {
  return SURFACES.find((s) => s.slug === slug)
}
