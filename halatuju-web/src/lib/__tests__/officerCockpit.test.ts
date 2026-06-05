import {
  factTileTone,
  groupDocumentsByFact,
  aiSuggestionFor,
  documentPill,
  documentFacts,
  incomeDocLayout,
} from '@/lib/officerCockpit'
import type { AdminVerdictFact, AdminApplicantDocument } from '@/lib/admin-api'

// ── Factories ─────────────────────────────────────────────────────────────────

function fact(
  f: AdminVerdictFact['fact'],
  status: AdminVerdictFact['status'],
): AdminVerdictFact {
  return { fact: f, status, evidence: [], unresolved: [] }
}

function doc(over: Partial<AdminApplicantDocument> = {}): AdminApplicantDocument {
  return {
    id: 1,
    doc_type: 'ic',
    original_filename: 'ic.pdf',
    size: 1024,
    verification_status: 'pending',
    download_url: null,
    vision_nric: '',
    vision_name: '',
    vision_address: '',
    vision_run_at: null,
    vision_error: '',
    vision_nric_verdict: '',
    vision_name_verdict: '',
    vision_name_match: '',
    vision_address_match: '',
    ...over,
  }
}

// ── factTileTone ──────────────────────────────────────────────────────────────

describe('factTileTone', () => {
  it('returns green for verified', () => {
    expect(factTileTone('verified')).toBe('green')
  })

  it('returns amber for review', () => {
    expect(factTileTone('review')).toBe('amber')
  })

  it('returns blue for recommend', () => {
    expect(factTileTone('recommend')).toBe('blue')
  })

  it('returns red for gap', () => {
    expect(factTileTone('gap')).toBe('red')
  })
})

// ── groupDocumentsByFact ──────────────────────────────────────────────────────

describe('groupDocumentsByFact', () => {
  it('places the student ic in identity', () => {
    const groups = groupDocumentsByFact([doc({ doc_type: 'ic' })])
    expect(groups.identity).toHaveLength(1)
    expect(groups.income).toHaveLength(0)
  })

  it('places results_slip in academic', () => {
    const groups = groupDocumentsByFact([doc({ doc_type: 'results_slip' })])
    expect(groups.academic).toHaveLength(1)
  })

  it('places income docs AND the parent ic in income', () => {
    // The parent/guardian IC moved to income — it confirms the earner whose name
    // the STR / salary slip / EPF are issued in.
    const incomeTypes = ['parent_ic', 'str', 'epf', 'salary_slip', 'water_bill', 'electricity_bill']
    const docs = incomeTypes.map((t, i) => doc({ id: i, doc_type: t }))
    const groups = groupDocumentsByFact(docs)
    expect(groups.income).toHaveLength(6)
    expect(groups.identity).toHaveLength(0)
  })

  it('places offer_letter in pathway', () => {
    const groups = groupDocumentsByFact([doc({ doc_type: 'offer_letter' })])
    expect(groups.pathway).toHaveLength(1)
  })

  it('places unrecognised types in other', () => {
    const groups = groupDocumentsByFact([doc({ doc_type: 'bank_statement' })])
    expect(groups.other).toHaveLength(1)
  })

  it('handles an empty list', () => {
    const groups = groupDocumentsByFact([])
    expect(groups.identity).toHaveLength(0)
    expect(groups.other).toHaveLength(0)
  })
})

// ── aiSuggestionFor ───────────────────────────────────────────────────────────

describe('aiSuggestionFor', () => {
  it('maps verified → yes', () => {
    const result = aiSuggestionFor([fact('identity', 'verified')])
    expect(result.identity).toBe('yes')
  })

  it('maps gap → no', () => {
    const result = aiSuggestionFor([fact('income', 'gap')])
    expect(result.income).toBe('no')
  })

  it('maps review → unsure', () => {
    const result = aiSuggestionFor([fact('academic', 'review')])
    expect(result.academic).toBe('unsure')
  })

  it('maps recommend → unsure', () => {
    const result = aiSuggestionFor([fact('pathway', 'recommend')])
    expect(result.pathway).toBe('unsure')
  })

  it('defaults to unsure when a fact is missing from the list', () => {
    const result = aiSuggestionFor([fact('identity', 'verified')])
    expect(result.academic).toBe('unsure')
    expect(result.income).toBe('unsure')
    expect(result.pathway).toBe('unsure')
  })

  it('handles all four facts in one pass', () => {
    const result = aiSuggestionFor([
      fact('identity', 'verified'),
      fact('academic', 'gap'),
      fact('income', 'review'),
      fact('pathway', 'recommend'),
    ])
    expect(result).toEqual({ identity: 'yes', academic: 'no', income: 'unsure', pathway: 'unsure' })
  })
})

// ── Check fixtures (only the fields the fact logic reads matter) ───────────────
const icCheck = (o: Partial<NonNullable<AdminApplicantDocument['income_ic_check']>>) =>
  ({ nric: '', name: '', address: '', member: '', name_status: 'pending', readable: false, ...o } as NonNullable<AdminApplicantDocument['income_ic_check']>)
const strCheck = (o: Partial<NonNullable<AdminApplicantDocument['str_check']>>) =>
  ({ name: '', nric: '', status: '', year: '', amount: '', member: '', name_status: 'no_ref', nric_status: 'no_ref', current_status: 'current', ic_present: false, ...o } as NonNullable<AdminApplicantDocument['str_check']>)
const acadCheck = (o: Partial<NonNullable<AdminApplicantDocument['academic_check']>>) =>
  ({ name: 'pending', subjects: 'pending', results: 'pending', candidate_name: '', exam: '', exam_year: '', missing: [], mismatched: [], uncertain: [], slip_count: 1, ...o } as NonNullable<AdminApplicantDocument['academic_check']>)

// ── documentPill (rolls up the fact colours) ──────────────────────────────────

describe('documentPill', () => {
  it('unread when no fact can be assessed', () => {
    expect(documentPill(doc({ doc_type: 'ic' }))).toBe('unread')
  })

  it('verified when every assessable fact is verified', () => {
    expect(documentPill(doc({ doc_type: 'ic', vision_nric_verdict: 'match', vision_name_verdict: 'match' }))).toBe('verified')
  })

  it('verified when only one fact is known and it matches', () => {
    expect(documentPill(doc({ doc_type: 'ic', vision_nric_verdict: 'match', vision_name_verdict: '' }))).toBe('verified')
  })

  it('check when any fact mismatches', () => {
    expect(documentPill(doc({ doc_type: 'ic', vision_nric_verdict: 'mismatch', vision_name_verdict: 'match' }))).toBe('check')
  })

  it('check when a fact is partial', () => {
    expect(documentPill(doc({ doc_type: 'ic', vision_nric_verdict: 'match', vision_name_verdict: 'partial' }))).toBe('check')
  })

  it('earner IC is judged by its income relationship check — a readable IC is Verified, not the old false Unread', () => {
    expect(documentPill(doc({ doc_type: 'parent_ic', income_ic_check: icCheck({ member: 'mother', readable: true }) }))).toBe('verified')
  })

  it('str pill rolls up recipient/IC/currency', () => {
    expect(documentPill(doc({ doc_type: 'str', str_check: strCheck({ name_status: 'match', nric_status: 'match', current_status: 'current' }) }))).toBe('verified')
    expect(documentPill(doc({ doc_type: 'str', str_check: strCheck({ name_status: 'match', nric_status: 'match', current_status: 'stale' }) }))).toBe('check')
  })

  it('unread when the per-fact check has not run', () => {
    expect(documentPill(doc({ doc_type: 'salary_slip' }))).toBe('unread')
  })
})

// ── documentFacts (per-doc coloured labels — only what the doc provides) ───────

describe('documentFacts', () => {
  it('identity IC → Name + IC No', () => {
    expect(documentFacts(doc({ doc_type: 'ic', vision_name_verdict: 'match', vision_nric_verdict: 'match' })))
      .toEqual([{ key: 'name', status: 'verified' }, { key: 'ic_no', status: 'verified' }])
  })

  it('father earner IC → Name, IC No, Relationship (patronymic)', () => {
    expect(documentFacts(doc({ doc_type: 'parent_ic', income_ic_check: icCheck({ member: 'father', name_status: 'match', readable: true }) })))
      .toEqual([{ key: 'name', status: 'verified' }, { key: 'ic_no', status: 'verified' }, { key: 'relationship', status: 'verified' }])
  })

  it('mother earner IC → Name + IC No only (relationship lives on the birth certificate)', () => {
    expect(documentFacts(doc({ doc_type: 'parent_ic', income_ic_check: icCheck({ member: 'mother', name_status: 'unknown', readable: true }) })).map((f) => f.key))
      .toEqual(['name', 'ic_no'])
  })

  it('results slip → Name, Subjects, Results from the 3-check', () => {
    expect(documentFacts(doc({ doc_type: 'results_slip', academic_check: acadCheck({ name: 'match', subjects: 'partial', results: 'match' }) })))
      .toEqual([{ key: 'name', status: 'verified' }, { key: 'subjects', status: 'partial' }, { key: 'results', status: 'verified' }])
  })

  it('str → Recipient, IC No, Current', () => {
    expect(documentFacts(doc({ doc_type: 'str', str_check: strCheck({ name_status: 'match', nric_status: 'mismatch', current_status: 'stale' }) })))
      .toEqual([{ key: 'recipient', status: 'verified' }, { key: 'ic_no', status: 'not' }, { key: 'current', status: 'partial' }])
  })

  it('birth certificate → Child, Mother, Father (carries the mother relationship)', () => {
    expect(documentFacts(doc({ doc_type: 'birth_certificate', bc_check: { child_name: '', child_status: 'match', mother_name: '', mother_nric: '', mother_status: 'match', father_name: '', father_status: 'match', bc_number: '' } })).map((f) => f.key))
      .toEqual(['child', 'mother', 'father'])
  })

  it('utility bill → Address only', () => {
    expect(documentFacts(doc({ doc_type: 'water_bill', utility_check: { name: '', address: '', monthly_bill: '', unpaid_balance: '', address_status: 'found' } })))
      .toEqual([{ key: 'address', status: 'verified' }])
  })

  it('returns [] when the check has not run', () => {
    expect(documentFacts(doc({ doc_type: 'str' }))).toEqual([])
  })
})

// ── incomeDocLayout ───────────────────────────────────────────────────────────

describe('incomeDocLayout', () => {
  it('STR + mother → STR doc → earner IC → birth certificate slots; missing ones are null', () => {
    const str = doc({ id: 1, doc_type: 'str' })
    const layout = incomeDocLayout({ income_route: 'str', income_earner: 'mother' }, [str])
    expect(layout.required.map((s) => [s.docType, s.doc?.id ?? null])).toEqual([
      ['str', 1],
      ['parent_ic', null],          // not uploaded → placeholder
      ['birth_certificate', null],  // mother → BC required
    ])
  })

  it('STR + father → no birth certificate slot (patronymic)', () => {
    const layout = incomeDocLayout({ income_route: 'str', income_earner: 'father' }, [])
    expect(layout.required.map((s) => s.docType)).toEqual(['str', 'parent_ic'])
  })

  it('salary + father & mother → per-member IC + salary slip, one untagged BC; extras go optional', () => {
    const fIc = doc({ id: 1, doc_type: 'parent_ic', household_member: 'father' })
    const fSlip = doc({ id: 2, doc_type: 'salary_slip', household_member: 'father' })
    const water = doc({ id: 9, doc_type: 'water_bill' })
    const layout = incomeDocLayout(
      { income_route: 'salary', income_working_members: ['father', 'mother'] },
      [fIc, fSlip, water],
    )
    expect(layout.required.map((s) => [s.docType, s.member, s.doc?.id ?? null])).toEqual([
      ['parent_ic', 'father', 1],
      ['salary_slip', 'father', 2],
      ['parent_ic', 'mother', null],
      ['salary_slip', 'mother', null],
      ['birth_certificate', '', null],   // mother needs a BC (untagged), not uploaded
    ])
    expect(layout.optional.map((d) => d.id)).toEqual([9])   // the water bill
  })
})
