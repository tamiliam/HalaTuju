/**
 * @jest-environment jsdom
 *
 * TD-403 (owner ruling 2026-10-26) — the student's STR chips by YEAR. An earlier year's STR reads
 * "needs this year's STR" (`stale`); a LATER year's page (`future` — likely next year's application
 * status) asks for this year's STR in neutral words and is never called stale, approved or a
 * mismatch. `t` echoes its key, so the assertions read against i18n keys.
 */
import { render, screen } from '@testing-library/react'
import { StrChecklist } from './checklists'
import type { ApplicantDocument, StrCheck } from '@/lib/api'

const t = (key: string) => key

function strDoc(current_status: StrCheck['current_status'], status = 'Lulus'): ApplicantDocument {
  const str_check: StrCheck = {
    name: 'DEVARAJ A/L MUNUSAMY', nric: '700707-14-5671', status, year: '2027', member: 'father',
    name_status: 'match', nric_status: 'match', current_status, ic_present: true,
  }
  return { id: 1, doc_type: 'str', str_check } as unknown as ApplicantDocument
}

describe('StrChecklist — the year rows (TD-403)', () => {
  test('an earlier year asks for this year\'s STR on the Year row, and claims no approval', () => {
    // 'stale' is any earlier year's page, read status or not (review of 0d32b712).
    render(<StrChecklist doc={strDoc('stale', '')} t={t} />)
    expect(screen.getAllByText('scholarship.docs.strCheck.stale')).toHaveLength(1)   // Year row only
    expect(screen.queryByText('scholarship.docs.strCheck.approved')).toBeNull()
    expect(screen.queryByText('scholarship.docs.strCheck.future')).toBeNull()
  })

  test('a later year\'s page is neutral: no status chip, never stale or approved', () => {
    render(<StrChecklist doc={strDoc('future', 'berjaya')} t={t} />)
    expect(screen.getByText('scholarship.docs.strCheck.future')).toBeTruthy()
    expect(screen.queryByText('scholarship.docs.strCheck.stale')).toBeNull()
    expect(screen.queryByText('scholarship.docs.strCheck.approved')).toBeNull()
  })

  test('this year still reads Current', () => {
    render(<StrChecklist doc={strDoc('current')} t={t} />)
    expect(screen.getByText('scholarship.docs.strCheck.current')).toBeTruthy()
  })
})

describe('StrChecklist — the display words (TD-742, owner ruling 25 Nov 2026)', () => {
  function displayDoc(extra: Partial<StrCheck>): ApplicantDocument {
    const doc = strDoc('current')
    return { ...doc, str_check: { ...doc.str_check, ...extra } } as ApplicantDocument
  }

  test('a recipient not read shows grey "Not read", never the green IC match', () => {
    render(<StrChecklist doc={displayDoc({ display_name_status: 'not_read', display_nric_status: 'match' })} t={t} />)
    expect(screen.getByText('scholarship.docs.incomeProofCheck.notRead')).toBeTruthy()
    expect(screen.getAllByText('scholarship.docs.incomeProofCheck.matchesIc')).toHaveLength(1)   // IC No row only
  })

  test('a clean disagreement shows red on the STR itself', () => {
    render(<StrChecklist doc={displayDoc({ display_name_status: 'mismatch', display_nric_status: 'mismatch' })} t={t} />)
    expect(screen.getAllByText('scholarship.docs.incomeProofCheck.mismatchIc')).toHaveLength(2)
  })

  test('an older payload without display fields reads the decision fields', () => {
    render(<StrChecklist doc={strDoc('current')} t={t} />)
    expect(screen.getAllByText('scholarship.docs.incomeProofCheck.matchesIc')).toHaveLength(2)
    expect(screen.queryByText('scholarship.docs.incomeProofCheck.notRead')).toBeNull()
  })
})
