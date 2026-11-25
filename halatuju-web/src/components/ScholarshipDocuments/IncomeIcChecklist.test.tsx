/**
 * @jest-environment jsdom
 *
 * TD-742 linkage Phase 1 (owner ruling 25 Nov 2026, adversarial review round 1): the parent IC card
 * the student sees. A clash with the income proof shows on the PROOF, so the card stays neutral;
 * but a truly wrong card (`display_wrong_card`) stays red on the card's own rows, said against the
 * birth certificate. `t` echoes its key, so the assertions read against i18n keys. Fake values only.
 */
import { render, screen } from '@testing-library/react'
import { IncomeIcChecklist } from './checklists'
import type { ApplicantDocument, IncomeIcCheck } from '@/lib/api'

const t = (key: string) => key

function icDoc(extra: Partial<IncomeIcCheck>): ApplicantDocument {
  const income_ic_check = {
    member: 'mother', name: 'RAMAN A/L CONTOH', nric: '730101-04-5001', address: '',
    name_status: 'match', readable: true, proof_kind: 'str',
    proof_name_status: 'mismatch', proof_nric_status: 'mismatch', chain_verified: true, wrong_card: true,
    ...extra,
  } as IncomeIcCheck
  return { id: 1, doc_type: 'parent_ic', vision_run_at: '2026-11-25T00:00:00Z', income_ic_check } as unknown as ApplicantDocument
}

describe('IncomeIcChecklist — the wrong card (TD-742 ruling 3)', () => {
  test('a truly wrong card shows red rows on the card, named as a wrong card', () => {
    render(<IncomeIcChecklist doc={icDoc({ display_wrong_card: true, display_proof_name_status: 'mismatch',
      display_proof_nric_status: 'mismatch' })} t={t} />)
    expect(screen.getAllByText('scholarship.docs.incomeIcCheck.wrongCard')).toHaveLength(2)
    expect(screen.queryByText('scholarship.docs.icCheck.fromTheirIc')).toBeNull()
  })

  test('a clash that belongs to the proof leaves the card neutral', () => {
    render(<IncomeIcChecklist doc={icDoc({ display_wrong_card: false, display_proof_name_status: 'no_ref',
      display_proof_nric_status: 'no_ref' })} t={t} />)
    expect(screen.queryByText('scholarship.docs.incomeIcCheck.wrongCard')).toBeNull()
    expect(screen.queryByText('scholarship.docs.incomeIcCheck.proofMismatch')).toBeNull()
    expect(screen.getAllByText('scholarship.docs.icCheck.fromTheirIc')).toHaveLength(2)
  })
})
