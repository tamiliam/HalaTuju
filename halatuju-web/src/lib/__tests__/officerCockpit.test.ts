import {
  factTileTone,
  groupDocumentsByFact,
  aiSuggestionFor,
  documentPill,
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
  it('places ic and parent_ic in identity', () => {
    const docs = [doc({ doc_type: 'ic' }), doc({ id: 2, doc_type: 'parent_ic' })]
    const groups = groupDocumentsByFact(docs)
    expect(groups.identity).toHaveLength(2)
    expect(groups.academic).toHaveLength(0)
  })

  it('places results_slip in academic', () => {
    const groups = groupDocumentsByFact([doc({ doc_type: 'results_slip' })])
    expect(groups.academic).toHaveLength(1)
  })

  it('places income docs in income', () => {
    const incomeTypes = ['str', 'epf', 'salary_slip', 'water_bill', 'electricity_bill']
    const docs = incomeTypes.map((t, i) => doc({ id: i, doc_type: t }))
    const groups = groupDocumentsByFact(docs)
    expect(groups.income).toHaveLength(5)
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

// ── documentPill ──────────────────────────────────────────────────────────────

describe('documentPill', () => {
  describe('IC / parent IC', () => {
    it('returns unread when no vision signals present', () => {
      expect(documentPill(doc({ doc_type: 'ic' }))).toBe('unread')
    })

    it('returns verified when both nric and name match', () => {
      expect(
        documentPill(
          doc({
            doc_type: 'ic',
            vision_nric_verdict: 'match',
            vision_name_verdict: 'match',
          }),
        ),
      ).toBe('verified')
    })

    it('returns verified when only nric matches (name not yet checked)', () => {
      expect(
        documentPill(
          doc({
            doc_type: 'ic',
            vision_nric_verdict: 'match',
            vision_name_verdict: '',
          }),
        ),
      ).toBe('verified')
    })

    it('returns check when nric mismatches', () => {
      expect(
        documentPill(
          doc({
            doc_type: 'ic',
            vision_nric_verdict: 'mismatch',
            vision_name_verdict: 'match',
          }),
        ),
      ).toBe('check')
    })

    it('returns check when name is partial', () => {
      expect(
        documentPill(
          doc({
            doc_type: 'ic',
            vision_nric_verdict: 'match',
            vision_name_verdict: 'partial',
          }),
        ),
      ).toBe('check')
    })

    it('returns check when either field is unreadable', () => {
      expect(
        documentPill(
          doc({ doc_type: 'parent_ic', vision_nric_verdict: 'unreadable' }),
        ),
      ).toBe('check')
    })
  })

  describe('supporting documents', () => {
    it('returns unread when no signals', () => {
      expect(documentPill(doc({ doc_type: 'salary_slip' }))).toBe('unread')
    })

    it('returns verified when name is found', () => {
      expect(
        documentPill(
          doc({ doc_type: 'salary_slip', vision_name_match: 'found' }),
        ),
      ).toBe('verified')
    })

    it('returns check when name is not_found', () => {
      expect(
        documentPill(
          doc({ doc_type: 'results_slip', vision_name_match: 'not_found' }),
        ),
      ).toBe('check')
    })

    it('returns check when name is unreadable', () => {
      expect(
        documentPill(
          doc({ doc_type: 'str', vision_name_match: 'unreadable' }),
        ),
      ).toBe('check')
    })

    it('returns verified when address is found (even if name blank)', () => {
      expect(
        documentPill(
          doc({ doc_type: 'water_bill', vision_address_match: 'found' }),
        ),
      ).toBe('verified')
    })
  })
})
