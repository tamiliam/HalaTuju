/**
 * @jest-environment jsdom
 *
 * THE STUDENT'S POST-CONSENT READ-BACK — where her documents are filed.
 *
 * This is TD-262 / W5, and it is the reason the finding mattered. `ScholarshipReview` carried its
 * own private `DOC_CATEGORY` map, one of THREE copies of "which fact does this document type
 * belong to". When the income-support letter became income evidence on 2026-07-25 (the owner's
 * fourth way: a declared amount backed by a school / ketua-kampung / penghulu / employer letter)
 * only the officer cockpit's copy was corrected, on 2026-09-07. So the one document proving an
 * informally-employed parent's wage sat under "Additional documents" on the confirmation screen
 * the student is asked to check before she submits. Real student: Janani.
 *
 * All three readers now share `@/lib/docCategory`. This file asserts what she SEES: the letter
 * under Household income, and a genuine extra still under Additional documents — because a fix
 * that swept everything into Income would be the same defect pointing the other way.
 *
 * `t` echoes its key (the house pattern), so assertions read against i18n keys and a copy change
 * never breaks this file.
 */
import { render, screen, waitFor, within } from '@testing-library/react'

import ScholarshipReview from './ScholarshipReview'
import { sandboxApplication, sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'
import type { ApplicantDocument, ScholarshipApplication, StudentProfile } from '@/lib/api'
import * as api from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  listDocuments: jest.fn(),
  getConsentStatus: jest.fn(),
}))

const mockApi = api as jest.Mocked<typeof api>

const SECTION = (cat: string) => `scholarship.docs.section.${cat}.title`
const TYPE = (docType: string) => `scholarship.docs.type.${docType}`

const doc = (id: number, docType: string): ApplicantDocument => ({
  id,
  doc_type: docType,
  original_filename: `${docType}.pdf`,
  content_type: 'application/pdf',
  size: 1024,
  verification_status: 'pending',
  uploaded_at: '2026-06-01T09:00:00.000Z',
  download_url: null,
} as unknown as ApplicantDocument)

/** The group block around a section heading: the heading's own parent holds its document rows. */
const group = (cat: string): HTMLElement => {
  const heading = screen.getByText(SECTION(cat))
  const block = heading.parentElement
  if (!block) throw new Error(`the ${cat} heading has no group around it`)
  return block
}

const review = async (documents: ApplicantDocument[]) => {
  mockApi.listDocuments.mockResolvedValue({ documents })
  mockApi.getConsentStatus.mockResolvedValue(
    { is_minor: false, consents: [] } as unknown as api.ConsentStatus)
  render(
    <ScholarshipReview
      app={sandboxApplication as ScholarshipApplication}
      profile={sandboxProfileSpm as unknown as StudentProfile}
      token="sandbox-token"
      onEdit={jest.fn()}
      onBack={jest.fn()}
      onSubmit={jest.fn()}
      submitting={false}
      submitError={null}
      canSubmit
      confirmed
      t={(k: string) => k}
      lang="en"
    />,
  )
  await waitFor(() => expect(screen.getByText(SECTION('identity'))).toBeTruthy())
}

beforeEach(() => {
  jest.clearAllMocks()
})

describe('the read-back files each document under the fact it proves', () => {
  it('⚠ THE INCOME-SUPPORT LETTER IS UNDER HOUSEHOLD INCOME, NOT "ADDITIONAL"', async () => {
    await review([doc(1, 'ic'), doc(2, 'income_support_doc'), doc(3, 'photo')])
    expect(within(group('income')).getByText(TYPE('income_support_doc'), { exact: false }))
      .toBeTruthy()
    expect(within(group('other')).queryByText(TYPE('income_support_doc'), { exact: false }))
      .toBeNull()
  })

  it('and a genuine extra still lands under Additional documents', async () => {
    // The control. Without it the assertion above also passes on a map that filed EVERYTHING
    // under income, which is the same defect pointing the other way.
    await review([doc(1, 'ic'), doc(2, 'income_support_doc'), doc(3, 'photo')])
    expect(within(group('other')).getByText(TYPE('photo'), { exact: false })).toBeTruthy()
    expect(within(group('income')).queryByText(TYPE('photo'), { exact: false })).toBeNull()
  })

  it('the current-semester result slip is an ACADEMIC document, as both other readers say', async () => {
    // The second neglected type: `semester_result` was in the cockpit's map and in `view.tsx`'s
    // (both 'academic') and missing from this one, so it fell through to "Additional documents".
    await review([doc(1, 'ic'), doc(4, 'semester_result')])
    expect(within(group('academic')).getByText(TYPE('semester_result'), { exact: false }))
      .toBeTruthy()
    expect(screen.queryByText(SECTION('other'))).toBeNull()
  })

  it('the ordinary income documents are undisturbed', async () => {
    // The payslip and the parent IC were always right; a change to the map must not move them.
    await review([doc(1, 'ic'), doc(5, 'salary_slip'), doc(6, 'parent_ic'), doc(7, 'offer_letter')])
    for (const docType of ['salary_slip', 'parent_ic']) {
      expect(within(group('income')).getByText(TYPE(docType), { exact: false })).toBeTruthy()
    }
    expect(within(group('identity')).getByText(TYPE('ic'), { exact: false })).toBeTruthy()
    expect(within(group('pathway')).getByText(TYPE('offer_letter'), { exact: false })).toBeTruthy()
  })

  it('a group with nothing in it draws no heading at all', async () => {
    // A heading over nothing reads as a screen that failed to load.
    await review([doc(1, 'ic')])
    for (const cat of ['academic', 'pathway', 'income', 'other']) {
      expect(screen.queryByText(SECTION(cat))).toBeNull()
    }
  })
})
