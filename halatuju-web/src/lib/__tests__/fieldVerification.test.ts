import { fieldVerifications } from '../fieldVerification'

// Minimal document fixtures — only the fields documentFacts() reads for each type.
const app = (documents: unknown[]) => ({ documents }) as never

describe('fieldVerifications', () => {
  it('returns nothing when there are no documents', () => {
    expect(fieldVerifications(app([]))).toEqual({})
  })

  it('ticks name + nric from a matched MyKad, sourced to mykad', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'ic', vision_name_verdict: 'match', vision_nric_verdict: 'match' },
    ]))
    expect(fv.name).toEqual({ source: 'mykad' })
    expect(fv.nric).toEqual({ source: 'mykad' })
  })

  it('ticks only the fact that matches (name match, nric mismatch → name only)', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'ic', vision_name_verdict: 'match', vision_nric_verdict: 'mismatch' },
    ]))
    expect(fv.name).toEqual({ source: 'mykad' })
    expect(fv.nric).toBeUndefined()
  })

  it('ticks school from a matched school-leaving certificate', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'school_leaving_cert', school_leaving_check: { school_status: 'match', name_status: 'match', nric_status: 'match', kelakuan_status: 'good' } },
    ]))
    expect(fv.school).toEqual({ source: 'schoolLeavingCert' })
  })

  it('does NOT tick school on a school mismatch', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'school_leaving_cert', school_leaving_check: { school_status: 'mismatch', name_status: 'match', nric_status: 'match', kelakuan_status: 'good' } },
    ]))
    expect(fv.school).toBeUndefined()
  })

  it('ticks grades from a matched results slip', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'results_slip', academic_check: { name: 'match', subjects: 'match', results: 'match' } },
    ]))
    expect(fv.grades).toEqual({ source: 'resultsSlip' })
  })

  it('ticks chosenProgramme + reportingDate from a genuine offer that carries a reporting date', () => {
    // reporting_official NOT required — the reporting date is READ off the offer (the #137 case).
    const fv = fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'genuine' }, pathway_check: { name: 'match', ic: 'match', pathway: 'match', reporting_date: '22 Jun 2026', reporting_official: false } },
    ]))
    expect(fv.chosenProgramme).toEqual({ source: 'offerLetter' })
    expect(fv.reportingDate).toEqual({ source: 'offerLetter' })
  })

  it('ticks preUInstitution when a genuine offer institution matches the declared one', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'genuine' }, pathway_check: { institution_status: 'match' } },
    ]))
    expect(fv.preUInstitution).toEqual({ source: 'offerLetter' })
  })

  it('does NOT tick preUInstitution on an institution clash / unknown / suspect offer', () => {
    expect(fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'genuine' }, pathway_check: { institution_status: 'clash' } },
    ])).preUInstitution).toBeUndefined()
    expect(fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'genuine' }, pathway_check: { institution_status: 'unknown' } },
    ])).preUInstitution).toBeUndefined()
    expect(fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'suspect' }, pathway_check: { institution_status: 'match' } },
    ])).preUInstitution).toBeUndefined()
  })

  it('does NOT tick preUInstitution when the offer is an overall pathway mismatch (#117 stream clash)', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'genuine' }, pathway_check: { institution_status: 'match', pathway: 'mismatch' } },
    ]))
    expect(fv.preUInstitution).toBeUndefined()
  })

  it('does NOT tick reportingDate when the offer carries no reporting date', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'genuine' }, pathway_check: { name: 'match', ic: 'match', pathway: 'match' } },
    ]))
    expect(fv.reportingDate).toBeUndefined()
  })

  it('does NOT tick reportingDate when the offer is suspect/fake', () => {
    const suspect = fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'suspect' }, pathway_check: { reporting_date: '22 Jun 2026' } },
    ]))
    expect(suspect.reportingDate).toBeUndefined()
    const fake = fieldVerifications(app([
      { doc_type: 'offer_letter', authenticity: { status: 'not_offer_letter' }, pathway_check: { reporting_date: '22 Jun 2026' } },
    ]))
    expect(fake.reportingDate).toBeUndefined()
  })

  it('ticks address from a utility bill whose address is found', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'water_bill', utility_check: { address_status: 'found' } },
    ]))
    expect(fv.address).toEqual({ source: 'utilityBill' })
  })

  it('ticks parentName from a readable parent IC', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'parent_ic', income_ic_check: { readable: true, member: 'father', name_status: 'match' } },
    ]))
    expect(fv.parentName).toEqual({ source: 'parentIc' })
  })

  it('ticks str only when approved AND current', () => {
    const current = fieldVerifications(app([
      { doc_type: 'str', str_check: { name_status: 'match', nric_status: 'match', current_status: 'current' } },
    ]))
    expect(current.str).toEqual({ source: 'strDoc' })

    const undated = fieldVerifications(app([
      { doc_type: 'str', str_check: { name_status: 'match', nric_status: 'match', current_status: 'unconfirmed' } },
    ]))
    expect(undated.str).toBeUndefined() // approved but not dated → no tick
  })

  it('ignores a superseded (replaced) document', () => {
    const fv = fieldVerifications(app([
      { doc_type: 'ic', vision_name_verdict: 'match', vision_nric_verdict: 'match', superseded_at: '2026-07-01T00:00:00Z' },
    ]))
    expect(fv.name).toBeUndefined()
  })
})
