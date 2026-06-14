import {
  factTileTone,
  groupDocumentsByFact,
  aiSuggestionFor,
  documentPill,
  documentFacts,
  incomeDocLayout,
  docIconFor,
  earnerMemberFor,
  viewerKind,
  verdictReliability,
} from '@/lib/officerCockpit'
import type { AdminVerdictFact, AdminApplicantDocument } from '@/lib/admin-api'

// ── Factories ─────────────────────────────────────────────────────────────────

function fact(
  f: AdminVerdictFact['fact'],
  status: AdminVerdictFact['status'],
  evidenceCodes: string[] = [],
): AdminVerdictFact {
  return {
    fact: f,
    status,
    evidence: evidenceCodes.map((code) => ({ code, params: {} })),
    unresolved: [],
  }
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
    expect(factTileTone(fact('identity', 'verified'))).toBe('green')
  })

  it('returns blue (Probable) for review backed by a verified value', () => {
    expect(factTileTone(fact('identity', 'review', ['nric_match']))).toBe('blue')
  })

  it('returns amber (Unsure) for review with NO verified value — blue needs a green', () => {
    expect(factTileTone(fact('income', 'review'))).toBe('amber')
  })

  it('treats a declared-only / soft-signal value as not verified (amber, not blue)', () => {
    expect(factTileTone(fact('pathway', 'review', ['pathway_declared']))).toBe('amber')
    expect(factTileTone(fact('income', 'review', ['utility_percapita_b40']))).toBe('amber')
  })

  it('returns amber (Unsure) for recommend', () => {
    expect(factTileTone(fact('income', 'recommend'))).toBe('amber')
  })

  it('returns red for gap', () => {
    expect(factTileTone(fact('identity', 'gap'))).toBe('red')
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
    // the STR / salary slip / EPF are issued in. The relationship docs (birth cert /
    // guardianship letter) link that earner to the student, so they're income too.
    const incomeTypes = ['parent_ic', 'str', 'epf', 'salary_slip', 'birth_certificate',
                         'guardianship_letter', 'water_bill', 'electricity_bill']
    const docs = incomeTypes.map((t, i) => doc({ id: i, doc_type: t }))
    const groups = groupDocumentsByFact(docs)
    expect(groups.income).toHaveLength(8)
    expect(groups.other).toHaveLength(0)
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
    // Nothing read (recipient/IC no_ref + current 'unknown') → unread, NOT a false Verified.
    expect(documentPill(doc({ doc_type: 'str', str_check: strCheck({ current_status: 'unknown' }) }))).toBe('unread')
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

  it('utility bill → Address, Current, Reasonable (Outstanding only when arrears > charge)', () => {
    const util = (o: Partial<NonNullable<AdminApplicantDocument['utility_check']>>) =>
      ({ name: '', address: '', monthly_bill: '', unpaid_balance: '', address_status: '',
        current_status: 'unknown', reasonable_status: 'unknown', reasonable_detail: '',
        outstanding_status: '', name_note: '', ...o } as NonNullable<AdminApplicantDocument['utility_check']>)
    // Address found, recent bill, both bills cheap, arrears exceed the charge → all four green.
    expect(documentFacts(doc({ doc_type: 'water_bill', utility_check: util({
      address_status: 'found', current_status: 'current', reasonable_status: 'reasonable', outstanding_status: 'arrears' }) })))
      .toEqual([
        { key: 'address', status: 'verified' },
        { key: 'current', status: 'verified' },
        { key: 'reasonable', status: 'verified' },
        { key: 'outstanding', status: 'verified' },
      ])
    // Stale bill, only one bill provided, no arrears → Current amber, Reasonable grey, no Outstanding.
    // Address 'unconfirmed' (couldn't confirm — bilingual town / abbreviation / partial OCR) is
    // AMBER, not red: only a true 'mismatch' (a different home) is red.
    expect(documentFacts(doc({ doc_type: 'electricity_bill', utility_check: util({
      address_status: 'unconfirmed', current_status: 'stale', reasonable_status: 'partial', reasonable_detail: 'electricity_only' }) })))
      .toEqual([
        { key: 'address', status: 'partial' },
        { key: 'current', status: 'partial' },
        { key: 'reasonable', status: 'unknown' },
      ])
    // Only a genuine 'mismatch' (different home) is red.
    expect(documentFacts(doc({ doc_type: 'water_bill', utility_check: util({ address_status: 'mismatch' }) }))
      .find((f) => f.key === 'address')?.status).toBe('not')
    // High combined consumption stays amber (soft proxy, never red).
    expect(documentFacts(doc({ doc_type: 'water_bill', utility_check: util({ reasonable_status: 'high' }) })).find((f) => f.key === 'reasonable')?.status)
      .toBe('partial')
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

  it('an uploaded birth certificate fills the slot (must be grouped into income first)', () => {
    // Regression: birth_certificate was missing from docTypeToFact's income case, so it
    // landed in 'other' and the income panel never saw it → showed a false "Missing".
    const bc = doc({ id: 7, doc_type: 'birth_certificate', household_member: '' })
    const layout = incomeDocLayout({ income_route: 'str', income_earner: 'mother' }, [bc])
    expect(layout.required.find((s) => s.docType === 'birth_certificate')?.doc?.id).toBe(7)
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

  it('optional bucket is canonically ordered: salary → EPF → BC → guardian → utilities', () => {
    // Uploaded in a jumbled order; the layout sorts them to mirror the student wizard.
    const elec = doc({ id: 1, doc_type: 'electricity_bill' })
    const epf = doc({ id: 2, doc_type: 'epf' })
    const bc = doc({ id: 3, doc_type: 'birth_certificate' })   // e.g. a mononym father-link proof
    const salary = doc({ id: 4, doc_type: 'salary_slip' })
    const water = doc({ id: 5, doc_type: 'water_bill' })
    // STR + father → only str/parent_ic are "required"; everything else is optional.
    const layout = incomeDocLayout({ income_route: 'str', income_earner: 'father' },
      [elec, epf, bc, salary, water])
    expect(layout.optional.map((d) => d.doc_type)).toEqual(
      ['salary_slip', 'epf', 'birth_certificate', 'water_bill', 'electricity_bill'])
  })
})

describe('docIconFor — per-doc-type glyph', () => {
  it('gives a distinct glyph per type, default for unknown', () => {
    expect(docIconFor('ic')).toBe('🪪')
    expect(docIconFor('results_slip')).toBe('🎓')
    expect(docIconFor('str')).toBe('💵')
    expect(docIconFor('water_bill')).toBe('💧')
    expect(docIconFor('something_else')).toBe('📄')   // safe default
  })
})

describe('earnerMemberFor — earner-IC label member', () => {
  it('uses the doc household_member tag (salary route)', () => {
    expect(earnerMemberFor('parent_ic', 'father', 'salary', '')).toBe('father')
  })
  it('falls back to the application income_earner for the UNTAGGED STR-route earner IC', () => {
    expect(earnerMemberFor('parent_ic', '', 'str', 'mother')).toBe('mother')
  })
  it('returns empty when it cannot be derived', () => {
    expect(earnerMemberFor('parent_ic', '', 'salary', '')).toBe('')
    expect(earnerMemberFor('ic', '', 'str', 'mother')).toBe('')   // not an earner IC
  })
  it('person-qualifies all STR income docs (str/salary_slip/epf), tag or earner fallback', () => {
    expect(earnerMemberFor('salary_slip', 'father', 'salary', '')).toBe('father')   // by tag
    expect(earnerMemberFor('str', '', 'str', 'mother')).toBe('mother')              // STR earner fallback
    expect(earnerMemberFor('epf', '', 'str', 'mother')).toBe('mother')
    expect(earnerMemberFor('salary_slip', '', 'str', 'father')).toBe('father')
  })
})

describe('viewerKind — how the in-cockpit viewer renders a doc', () => {
  it('pdf by content-type or extension', () => {
    expect(viewerKind('application/pdf', 'x')).toBe('pdf')
    expect(viewerKind('', 'STR.PDF')).toBe('pdf')
  })
  it('image for jpeg/png/etc', () => {
    expect(viewerKind('image/jpeg', 'a.jpg')).toBe('image')
    expect(viewerKind('image/png', 'b')).toBe('image')
    expect(viewerKind('', 'photo.JPEG')).toBe('image')
  })
  it('heic/heif is unsupported (browsers cannot render it)', () => {
    expect(viewerKind('image/heic', 'IMG.HEIC')).toBe('unsupported')
    expect(viewerKind('', 'pic.heif')).toBe('unsupported')
  })
  it('unknown types are unsupported', () => {
    expect(viewerKind('application/octet-stream', 'blob')).toBe('unsupported')
  })
})

describe('verdictReliability (the scorekeeper)', () => {
  it('computes per-fact + overall agreement as 1 - override rate', () => {
    const r = verdictReliability({
      applications: 12, fact_decisions: 44, overrides: 6, override_rate: 0.1364,
      per_fact: {
        identity: { decided: 12, overrides: 1 },
        academic: { decided: 12, overrides: 3 },
        pathway: { decided: 8, overrides: 1 },
        income: { decided: 12, overrides: 1 },
      },
    })
    expect(r.applications).toBe(12)
    const id = r.perFact.find((f) => f.fact === 'identity')!
    expect(id.agree).toBe(11)
    expect(id.pct).toBeCloseTo(11 / 12)
    expect(r.overall.agree).toBe(38)          // 44 decided - 6 overrides
    expect(r.overall.pct).toBeCloseTo(38 / 44)
  })

  it('handles zero decisions without divide-by-zero', () => {
    const r = verdictReliability({ applications: 0, fact_decisions: 0, overrides: 0, override_rate: 0, per_fact: {} })
    expect(r.overall.pct).toBe(0)
    expect(r.perFact).toHaveLength(4)
    expect(r.perFact.every((f) => f.pct === 0 && f.decided === 0)).toBe(true)
  })
})
