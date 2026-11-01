'use client'

/**
 * Scholarship apply, documents and award, mounted for mobile-check and the owner's phone review
 * (Mobile M4). Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in.
 *
 * Every surface mounts the REAL page or component over fixtures through the stubbed fetch — the
 * award page asks `/scholarship/award/` exactly as on the live site, and the answer is a fixture.
 * SIGN-IN IS SYNTHETIC: a hand-filled `AuthContext` (never `AuthProvider`, which would mint a real
 * anonymous user), a made-up user id, a made-up token the stub ignores. Nothing is sent anywhere —
 * the stub accepts writes and discards them.
 */
import { useState, type ReactNode } from 'react'
import ScholarshipApplyPage from '@/app/scholarship/apply/page'
import ScholarshipAwardPage from '@/app/scholarship/award/page'
import ScholarshipDocuments from '@/components/ScholarshipDocuments'
import RemoveConfirm from '@/components/ScholarshipDocuments/RemoveConfirm'
import { AuthContext } from '@/lib/auth-context'
import { APPLY_DRAFT_KEY, writeApplyDraft } from '@/lib/applyDraft'
import { profileToApplyDefaults } from '@/lib/scholarship'
import { sandboxApplication, sandboxNoApplications, sandboxProfileSpm } from './fixtures/scholarship'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface {
  slug: string; title: string; note: string; render: () => ReactNode; routes?: Record<string, () => unknown>
}

const TOKEN = 'sandbox-not-a-real-token'
const UID = 'sandbox-student-not-a-real-id'
const PROFILE = { ...sandboxProfileSpm, results_held: 'spm', nric: 'XXXXXX-XX-XXXX', nric_verified: true,
  contact_phone: '012-000 0000' }

function SignedIn({ children }: { children: ReactNode }) {
  return (
    <AuthContext.Provider value={{
      status: 'ready', isAuthenticated: true, isAnonymous: false, hasSession: true, token: TOKEN, profile: PROFILE,
      showAuthGate: () => {}, session: { user: { id: UID, email: 'pelajar@contoh.invalid' } },
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

/** A draft as the form keeps it, seeded before the page mounts if the tab has none — what a reload after an iOS tab
 *  kill finds in this tab: My Family, half done. (No IC, signature or consent — the draft holds none.) */
function DraftRestored() {
  useState(() => {
    try {
      // Only when this tab holds none: a reload of the surface then shows what SHE typed, restored.
      if (sessionStorage.getItem(APPLY_DRAFT_KEY)) return true
      writeApplyDraft({
        ...profileToApplyDefaults(PROFILE as never), referringOrg: 'other', phone: '012-000 0000',
        householdSize: '5', householdIncome: '2400', receivesStr: true,
        parentName: 'Kumaran a/l Raju', parentPhone: '012-345 6789',
      }, { uid: UID, programme: '' }, 'family')
    } catch { /* no storage: the page draws the empty form */ }
    return true
  })
  return <SignedIn><ScholarshipApplyPage /></SignedIn>
}

/** The agreement as the server renders it for PRINT (11 px, 9 px notes, two-column tables) — sample
 *  wording in the server's own markup, so the phone stylesheet is measured against the real shape. */
const AGREEMENT_HTML = '<html><head><meta charset="utf-8"/></head>'
  + '<body style="font-family: \'IBM Plex Serif\', Georgia, serif; font-size: 11px; color: black; line-height: 1.4;">'
  + '<div style="background:aliceblue; border:1px solid lightsteelblue; color:navy; padding:6px 10px; text-align:center; '
  + 'font-size:9px; margin-bottom:12px;">The English version of this Agreement is authoritative.</div>'
  + '<h1 style="font-size:18px; text-align:center; margin:0 0 4px 0;">Conditional Bursary Award Agreement</h1>'
  + '<h2 style="font-size:13px; margin:14px 0 6px 0;">Particulars / Butiran</h2>'
  + '<table style="width:100%; border-collapse:collapse; font-size:11px;">'
  + '<tr><td style="border:1px solid silver; padding:4px; width:40%;">Amount</td><td style="border:1px solid silver; padding:4px;">RM 6,000.00</td></tr>'
  + '<tr><td style="border:1px solid silver; padding:4px; width:40%;">Institution</td><td style="border:1px solid silver; padding:4px;">Universiti Contoh</td></tr></table>'
  + '<h2 style="font-size:13px; margin:16px 0 6px 0;">Terms / Terma</h2>'
  + '<p>1.1 "Bursary" means the sum of RM 6,000.00 paid in instalments under clause 2.</p>'
  + '<p>2.1 The Foundation will pay RM 500 a month for 12 months, starting in the month the Student enrols.</p>'
  + '<p>3.1 The Student will tell the Foundation within 14 days if she changes course or leaves.</p>'
  + '<table style="width:100%; border-collapse:collapse;"><tr>'
  + '<td style="width:50%; vertical-align:top; padding:8px;">Signed by the Student</td>'
  + '<td style="width:50%; vertical-align:top; padding:8px;">Signed by the Parent / Guardian</td></tr></table>'
  + '<p style="margin-top:14px; font-size:9px; color:gray;">Sample agreement for the design sandbox.</p></body></html>'

const OFFER = { amount: '6000.00', accept_deadline: '2026-12-15T00:00:00Z' }
const PREVIEW = {
  award_amount: '6000.00', payment_schedule: 'RM 500 a month, 12 months', institution_name: 'Universiti Contoh',
  course_name: 'Ijazah Sarjana Muda Sains Komputer', progress_standard: '', foundation_signatory_name: 'Pengerusi',
  foundation_signatory_title: 'Yayasan Contoh', rendered_html: AGREEMENT_HTML,
}
const award = (body: object) => ({
  '/api/v1/scholarship/award/': () => ({ offer: OFFER, finalising: false, acceptance_enabled: true, ...body }),
})

export const SCHOLARSHIP_APPLY_SURFACES: Surface[] = [
  {
    slug: 'apply-draft-restored',
    title: 'Apply — the draft, back after a reload',
    note: 'An iOS tab kill and a reload: the form comes back on My Family with what she typed, the '
      + '"Saved on this device only" line under the step, and the sticky Back / Continue bar. Her draft '
      + 'is seeded in this tab before the page mounts (a synthetic user id; no IC, signature or consent).',
    routes: { '/api/v1/scholarship/applications/': () => sandboxNoApplications },
    render: () => <DraftRestored />,
  },
  {
    slug: 'documents-remove',
    title: 'Documents — Remove asks first',
    note: 'The documents tab with the remove question open over it: the card\'s full-width 44 px Replace '
      + 'and Remove buttons beneath, the sheet\'s "Remove" and "Keep it" (focus on Keep it).',
    render: () => (
      <>
        <ScholarshipDocuments token={TOKEN} app={sandboxApplication} />
        <RemoveConfirm name="keputusan-spm.pdf" busy={false} onCancel={() => {}} onConfirm={() => {}} />
      </>
    ),
  },
  {
    slug: 'award-sign-adult',
    title: 'Award — read and sign (adult)',
    note: 'The bursary signing page after the quiz (the server says it was passed on this template): '
      + 'particulars stacked, "Read the full agreement", the signature, the parent PIN still to send, '
      + 'and the sticky "Sign and accept" with Decline beneath.',
    routes: award({ is_minor: false, bursary_preview: { ...PREVIEW, comprehension_passed: true, guarantor_phone_verified: false } }),
    render: () => <SignedIn><ScholarshipAwardPage /></SignedIn>,
  },
  {
    slug: 'award-sign-minor',
    title: 'Award — read and sign (under 18, PIN already checked)',
    note: 'The same page for a student under 18 (no student signature box — the guardian is the surety), '
      + 'after a reload inside the 30-minute PIN window: the PIN shows as verified, no second SMS offered.',
    routes: award({ is_minor: true, bursary_preview: { ...PREVIEW, comprehension_passed: true, guarantor_phone_verified: true } }),
    render: () => <SignedIn><ScholarshipAwardPage /></SignedIn>,
  },
  {
    slug: 'award-plain-minor',
    title: 'Award — plain offer (under 18)',
    note: 'The plain accept page (no agreement in play) for a student under 18: Accept opens the guardian '
      + 'form in a sheet that cannot be swiped away; Decline asks in a sheet.',
    routes: award({ is_minor: true }),
    render: () => <SignedIn><ScholarshipAwardPage /></SignedIn>,
  },
]
