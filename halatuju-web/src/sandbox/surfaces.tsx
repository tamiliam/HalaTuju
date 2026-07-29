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
import SponsorStudentsPage from '@/app/sponsor/(portal)/students/page'
import { SponsorPortalContext } from '@/lib/sponsor-portal-context'
import { sandboxApplication, sandboxApplicationLeanProgramme } from './fixtures/scholarship'
import { sandboxPool } from './fixtures/sponsor'

const SANDBOX_TOKEN = 'sandbox-not-a-real-token'

export interface Surface {
  slug: string
  title: string
  /** What a designer is looking at, and which state it is in — states are chosen, not accidental. */
  note: string
  render: () => ReactNode
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
