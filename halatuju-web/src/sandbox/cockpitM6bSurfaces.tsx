'use client'

/**
 * Mobile M6b, mounted for mobile-check and the owner's phone review: the REAL case page (`AdminScholarshipDetailView`)
 * inside the REAL console shell, with the cockpit fixtures. The case mid-review (the decision bar shows), the image
 * viewer, the PDF viewer (a phone opens the PDF in its own viewer), and a funded case whose payment ledger is
 * read-only on a phone.
 *
 * ⚠ IDENTITY IS SYNTHETIC (an `AdminAuthContext` value, never the provider, never a sign-in), and the network is
 * the sandbox stub: every write here goes nowhere. The address is the shell's sandbox-only `path`.
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and `mobile-check/targets.ts`
 * reads this file's list too.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { AppShell } from '@/components/admin/AppShell'
import { AdminScholarshipDetailView } from '@/app/admin/scholarship/[id]/view'
import { AdminAuthContext } from '@/lib/admin-auth-context'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { sandboxCockpitApplication, sandboxCockpitCaseSummary, sandboxCockpitInterview } from './fixtures/cockpit'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown> }

const ROLE = {
  is_admin: true, is_super_admin: false, role: 'org_admin', admin_id: 1,
  org_name: 'Yayasan Contoh', owning_org_id: 1, owning_org_name: 'Yayasan Contoh',
  admin_name: 'Pentadbir Contoh', reviewer_profile_complete: true,
  // The cockpit writes on the 'qc' key (`canWrite`), so the decision and ledger controls draw as they would for her.
  permissions: ['review', 'qc', 'see_all'],
}

const BASE = sandboxCockpitApplication as AdminScholarshipDetail
const docs = BASE.documents
/** A case whose FIRST document opens: an image (the IC) or a PDF (the payslip). Files are the site's own. */
const withFirstDoc = (kind: 'image' | 'pdf'): AdminScholarshipDetail => {
  const ic = docs.find((d) => d.doc_type === 'ic')!
  const pdf = docs.find((d) => d.content_type === 'application/pdf')!
  const first = kind === 'image'
    ? { ...ic, download_url: '/og-image.png', original_filename: 'ic_depan.jpg' }
    : { ...pdf, download_url: '/sandbox-not-a-real-file.pdf', original_filename: 'slip_gaji_mei.pdf' }
  return { ...BASE, documents: [first, ...docs.filter((d) => d.id !== first.id)] }
}
const FUNDED: AdminScholarshipDetail = {
  ...BASE, status: 'maintenance', maintenance_substate: 'on_track', has_file: false,
  disbursements: [
    { id: 1, sequence: 1, amount: '1200.00', status: 'released', label: 'Semester 1', scheduled_for: '2026-09-01',
      released_at: '2026-09-02T00:00:00Z', actioned_by: 'Pentadbir Contoh', reference: 'TR-1', note: '', sponsorship_id: null,
      created_at: '2026-08-20T00:00:00Z' },
    { id: 2, sequence: 2, amount: '1200.00', status: 'scheduled', label: 'Semester 2', scheduled_for: '2027-02-01',
      released_at: null, actioned_by: '', reference: '', note: '', sponsorship_id: null, created_at: '2026-08-20T00:00:00Z' },
  ],
} as AdminScholarshipDetail

const routesFor = (app: AdminScholarshipDetail): Record<string, () => unknown> => ({
  '/api/v1/admin/scholarship/applications/1/': () => app,
  '/api/v1/admin/scholarship/applications/1/verdict-summary/': () => sandboxCockpitCaseSummary,
  '/api/v1/admin/scholarship/applications/1/interview/': () => ({ session: sandboxCockpitInterview, agenda: [] }),
  '/api/v1/admin/scholarship/assignable-admins/': () => ({ admins: [] }),
  '/api/v1/admin/scholarship/sources/': () => ({ sources: [] }),
})

function Case({ children }: { children?: ReactNode }) {
  return (
    <AdminAuthContext.Provider value={{
      session: null, token: 'sandbox-not-a-real-token', isLoading: false, isAdminAuthenticated: true, role: ROLE as never,
      refreshRole: async () => {}, photoUrl: null, setPhotoUrl: () => {},
    } as never}>
      <AppShell path="/admin/scholarship/1"><AdminScholarshipDetailView applicationId={1} />{children}</AppShell>
    </AdminAuthContext.Provider>
  )
}

/** Taps a control once the page has drawn it (opens the viewer) — design review only. */
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

export const COCKPIT_PHONE_SURFACES: Surface[] = [
  {
    slug: 'cockpit-case',
    title: 'Cockpit — the case page on a phone (sections, the decision bar)',
    note: 'Mobile M6b: sections not cards, 44 px Previous / Next, documents as rows with no inner scroll box, and the '
      + 'sticky decision bar that shows the chosen outcome and JUMPS to the decision (Save stays there).',
    routes: routesFor(BASE),
    render: () => <Case />,
  },
  {
    slug: 'cockpit-viewer-image',
    title: 'Cockpit — the document viewer, an image',
    note: 'Mobile M6b: full screen, the image inline, a 44 px close and a 44 px "Open in new tab".',
    routes: routesFor(withFirstDoc('image')),
    render: () => <Case><TapOnce selector="[data-docs-list] li button[title]" /></Case>,
  },
  {
    slug: 'cockpit-viewer-pdf',
    title: 'Cockpit — the document viewer, a PDF',
    note: 'Mobile M6b (owner): on a phone a PDF opens in the phone\'s own viewer in a new tab — a 44 px Open, never an iframe.',
    routes: routesFor(withFirstDoc('pdf')),
    render: () => <Case><TapOnce selector="[data-docs-list] li button[title]" /></Case>,
  },
  {
    slug: 'cockpit-payments',
    title: 'Cockpit — the payment ledger, read-only on a phone',
    note: 'Mobile M6b (owner): on a phone the tranche actions and the Schedule form give way to a "use a computer" note.',
    routes: routesFor(FUNDED),
    render: () => <Case />,
  },
]
