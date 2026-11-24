/**
 * @jest-environment jsdom
 *
 * #78 review round 1 — a far name beside an IC number one digit off (`check_both`): both cells
 * were read and both are slightly wrong. The row reads amber with its own words, never the generic
 * "reviewing" line and never red. `t` echoes its key, so the assertions read against i18n keys.
 */
import { render, screen } from '@testing-library/react'
import { BcChecklist } from './checklists'
import type { ApplicantDocument } from '@/lib/api'

const t = (key: string) => key

const bcDoc = (mother_status: string) => ({
  id: 1, doc_type: 'birth_certificate',
  bc_check: { child_name: 'A CHILD', child_status: 'match', mother_name: 'A MOTHER', mother_nric: '800101-14-5002',
              mother_status, father_name: '', father_status: 'no_ref', bc_number: '', link: 'amber' },
}) as unknown as ApplicantDocument

describe('BcChecklist — the check_both row (#78)', () => {
  test('names the row as spelt differently with a one-digit-off number', () => {
    render(<BcChecklist doc={bcDoc('check_both')} t={t} />)
    expect(screen.getByText('scholarship.docs.relCheck.checkBoth')).toBeTruthy()
    expect(screen.queryByText('scholarship.docs.relCheck.reviewing')).toBeNull()
    expect(screen.queryByText('scholarship.docs.relCheck.mismatch')).toBeNull()
  })
})
