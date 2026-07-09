import {
  factTileTone,
  groupDocumentsByFact,
  aiSuggestionFor,
  documentPill,
  documentFacts,
  incomeDocLayout,
  incomeSubSections,
  docIconFor,
  earnerMemberFor,
  viewerKind,
  verdictReliability,
  isClearAccept,
  isQueryingLocked,
  isDecisionReady,
  isApproveReady,
  verdictItemKey,
  headerTimeline,
  type TimelineSource,
} from '@/lib/officerCockpit'
import type { AdminVerdictFact, AdminVerdictItem, AdminApplicantDocument } from '@/lib/admin-api'

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

  it('places results_slip AND semester_result in academic', () => {
    const groups = groupDocumentsByFact([
      doc({ id: 1, doc_type: 'results_slip' }), doc({ id: 2, doc_type: 'semester_result' })])
    expect(groups.academic).toHaveLength(2)
  })

  it('places statement_of_intent / photo / school_leaving_cert in additional', () => {
    const groups = groupDocumentsByFact(['statement_of_intent', 'photo', 'school_leaving_cert']
      .map((t, i) => doc({ id: i, doc_type: t })))
    expect(groups.additional).toHaveLength(3)
    expect(groups.other).toHaveLength(0)
  })

  it('orders academic: SPM results slip on top, semester (CGPA) slip below', () => {
    const groups = groupDocumentsByFact(['semester_result', 'results_slip']
      .map((t, i) => doc({ id: i, doc_type: t })))
    expect(groups.academic.map((d) => d.doc_type)).toEqual(['results_slip', 'semester_result'])
  })

  it('orders additional: school-leaving cert → statement of intent → photo', () => {
    // fed out of order, must come back in the fixed order
    const groups = groupDocumentsByFact(['photo', 'statement_of_intent', 'school_leaving_cert']
      .map((t, i) => doc({ id: i, doc_type: t })))
    expect(groups.additional.map((d) => d.doc_type)).toEqual([
      'school_leaving_cert', 'statement_of_intent', 'photo'])
  })

  it('places income_support_doc / bank_statement / reference_letter / other in other', () => {
    const groups = groupDocumentsByFact(['income_support_doc', 'bank_statement', 'reference_letter', 'other']
      .map((t, i) => doc({ id: i, doc_type: t })))
    expect(groups.other).toHaveLength(4)
    expect(groups.additional).toHaveLength(0)
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
    const groups = groupDocumentsByFact([doc({ doc_type: 'some_future_type' })])
    expect(groups.other).toHaveLength(1)
  })

  it('handles an empty list', () => {
    const groups = groupDocumentsByFact([])
    expect(groups.identity).toHaveLength(0)
    expect(groups.other).toHaveLength(0)
  })

  it('diverts superseded docs to the superseded bucket, out of every fact group', () => {
    const groups = groupDocumentsByFact([
      doc({ id: 1, doc_type: 'ic' }),                                    // live
      doc({ id: 2, doc_type: 'ic', superseded_at: '2026-07-04T00:00:00Z' }),  // replaced
      doc({ id: 3, doc_type: 'str', superseded_at: '2026-07-04T00:00:00Z' }), // replaced income doc
    ])
    expect(groups.identity).toHaveLength(1)   // only the live IC
    expect(groups.income).toHaveLength(0)     // the replaced STR is NOT a live income input
    expect(groups.superseded.map((d) => d.id)).toEqual([2, 3])
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
const pathCheck = (o: Partial<NonNullable<AdminApplicantDocument['pathway_check']>>) =>
  ({ name: 'match', ic: 'match', candidate_name: '', candidate_nric: '', programme: '', institution: '', issuer: '', offer_date: '', intake: '', address: '', pathway: 'match', declared_programme: '', declared_institution: '', ...o } as NonNullable<AdminApplicantDocument['pathway_check']>)

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

  it('str → Recipient, IC No, Status, Current (Status is the 3rd required variable)', () => {
    expect(documentFacts(doc({ doc_type: 'str', str_check: strCheck({ name_status: 'match', nric_status: 'mismatch', current_status: 'stale' }) })))
      .toEqual([
        { key: 'recipient', status: 'verified' },
        { key: 'ic_no', status: 'not' },
        { key: 'status', status: 'verified' },   // 'stale' is still approved (Lulus) → green
        { key: 'current', status: 'partial' },   // …but a prior-year cycle → amber
      ])
  })

  it('str Current chip is DATE-only — dated→green, prior-year→amber, else grey "we don\'t know"', () => {
    const cur = (s: string) =>
      documentFacts(doc({ doc_type: 'str', str_check: strCheck({ current_status: s }) }))
        .find((f) => f.key === 'current')!.status
    expect(cur('current')).toBe('verified')      // 🟢 dated this cycle
    expect(cur('stale')).toBe('partial')         // 🟡 prior-year (a real concern)
    expect(cur('unconfirmed')).toBe('unknown')   // ⚪ approved but no date → we don't know
    expect(cur('unreadable')).toBe('unknown')    // ⚪ couldn't tell
    expect(cur('rejected')).toBe('unknown')      // ⚪ date n/a (Status chip carries the red)
    expect(cur('wrong_type')).toBe('unknown')    // ⚪ date n/a (Status chip carries the red)
  })

  it('str Status chip = approval (Lulus), distinct from currency/date', () => {
    const stat = (s: string) =>
      documentFacts(doc({ doc_type: 'str', str_check: strCheck({ current_status: s }) }))
        .find((f) => f.key === 'status')!.status
    expect(stat('current')).toBe('verified')     // 🟢 Lulus
    expect(stat('stale')).toBe('verified')       // 🟢 Lulus (just an old cycle)
    expect(stat('unconfirmed')).toBe('verified') // 🟢 Lulus (just no date)
    expect(stat('rejected')).toBe('not')         // 🔴 Ditolak
    expect(stat('wrong_type')).toBe('not')       // 🔴 not an STR — no approval to show
    expect(stat('unreadable')).toBe('partial')   // 🟡 cropped — couldn't read the status line
  })

  it('semester result → Name + IC No (green on match, red otherwise) + CGPA (green found / grey none)', () => {
    // matched name + IC + a cumulative CGPA → all green
    expect(documentFacts(doc({ doc_type: 'semester_result',
      semester_check: { name: 'X', nric: 'Y', cgpa: '3.19', name_status: 'match', nric_status: 'match' } })))
      .toEqual([{ key: 'name', status: 'verified' }, { key: 'ic_no', status: 'verified' },
                { key: 'cgpa', status: 'verified' }])
    // name mismatch + no NRIC on slip + semester-only (no CGPA) → name red, IC red, CGPA grey (never flagged)
    expect(documentFacts(doc({ doc_type: 'semester_result',
      semester_check: { name: 'X', nric: '', cgpa: '', name_status: 'mismatch', nric_status: 'no_ref' } })))
      .toEqual([{ key: 'name', status: 'not' }, { key: 'ic_no', status: 'not' },
                { key: 'cgpa', status: 'unknown' }])
    // unread → no chips (row shows "Unread")
    expect(documentFacts(doc({ doc_type: 'semester_result' }))).toEqual([])
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

  it('electricity bill scored not_electricity_bill → red "Wrong type" chip + capped reads', () => {
    // The #83 case: a water bill (or MyKad/junk) in the electricity slot. The genuineness scorer
    // returns not_electricity_bill → the same red wrongType chip every other doc shows, and the
    // utility reads (off the wrong document) are capped red.
    const util = { name: '', address: '', monthly_bill: '', unpaid_balance: '', address_status: 'found',
      current_status: 'current', reasonable_status: 'reasonable', reasonable_detail: '',
      outstanding_status: '', name_note: '' } as NonNullable<AdminApplicantDocument['utility_check']>
    const facts = documentFacts(doc({ doc_type: 'electricity_bill', utility_check: util,
      authenticity: { status: 'not_electricity_bill', reason: 'water bill in the slot' } }))
    expect(facts.find((f) => f.key === 'wrongType')?.status).toBe('not')
    expect(facts.find((f) => f.key === 'address')?.status).toBe('not')   // capped — read off the wrong doc
    expect(facts.find((f) => f.key === 'current')?.status).toBe('not')
  })

  it('electricity bill scored genuine → no chip (renders normally)', () => {
    const util = { name: '', address: '', monthly_bill: '', unpaid_balance: '', address_status: 'found',
      current_status: 'current', reasonable_status: 'reasonable', reasonable_detail: '',
      outstanding_status: '', name_note: '' } as NonNullable<AdminApplicantDocument['utility_check']>
    const facts = documentFacts(doc({ doc_type: 'electricity_bill', utility_check: util,
      authenticity: { status: 'genuine', reason: '' } }))
    expect(facts.some((f) => f.key === 'wrongType')).toBe(false)
    expect(facts.find((f) => f.key === 'address')?.status).toBe('verified')
  })

  it('offer letter: a genuine official offer keeps Pathway green and no Official flag', () => {
    const facts = documentFacts(doc({ doc_type: 'offer_letter',
      pathway_check: pathCheck({ name: 'match', ic: 'match', pathway: 'match' }),
      authenticity: { status: 'genuine', reason: '' } }))
    expect(facts.find((f) => f.key === 'pathway')?.status).toBe('verified')
    expect(facts.some((f) => f.key === 'official')).toBe(false)
  })

  it('offer letter: a SUSPECT offer forces Pathway red + an AMBER Official flag', () => {
    // #31/#131 the pemakluman / interview slip: identity matches, programme tokens match, but
    // the doc is not confidently a genuine official offer → the Pathway VARIABLE is red (it
    // establishes no pathway — counted by the verdict's `_pathway_red_chips`), and Official is
    // AMBER (owner 2026-07-08: two-tone — suspect = "not sure", never branded fake). Pill → check.
    const d = doc({ doc_type: 'offer_letter',
      pathway_check: pathCheck({ name: 'match', ic: 'match', pathway: 'match' }),
      authenticity: { status: 'suspect', reason: 'pemakluman' } })
    const facts = documentFacts(d)
    expect(facts.find((f) => f.key === 'pathway')?.status).toBe('not')
    expect(facts.find((f) => f.key === 'official')?.status).toBe('partial')
    expect(documentPill(d)).toBe('check')   // never 'verified'
  })

  it('offer letter: a suspect doc WITH the validated summons keeps Pathway green (#56/#75)', () => {
    // The bonus lifts effective officialness: the doc provably summons registration at a public
    // institution → Pathway shows its real content status (green when matching), matching the
    // Certain tile. Official stays AMBER (raw genuineness — Check-2 still acts on it). NB there is
    // deliberately NO separate reporting-date chip (owner 2026-07-08: the Intake chip carries the
    // currency signal; the bonus is band machinery).
    const facts = documentFacts(doc({ doc_type: 'offer_letter',
      pathway_check: pathCheck({ name: 'match', ic: 'match', pathway: 'match',
                                 reporting_date: '20 Jul 2026', reporting_official: true,
                                 intake_year_status: 'current' }),
      authenticity: { status: 'suspect', reason: 'thin' } }))
    expect(facts.find((f) => f.key === 'pathway')?.status).toBe('verified')
    expect(facts.find((f) => f.key === 'official')?.status).toBe('partial')
    expect(facts.some((f) => f.key === 'daftar')).toBe(false)
  })

  it('offer letter: a FAKE doc stays Pathway red even with a summons (never green)', () => {
    const facts = documentFacts(doc({ doc_type: 'offer_letter',
      pathway_check: pathCheck({ name: 'match', ic: 'match', pathway: 'match',
                                 reporting_date: '8 Jun 2026', reporting_official: true }),
      authenticity: { status: 'not_offer_letter', reason: 'x' } }))
    expect(facts.find((f) => f.key === 'pathway')?.status).toBe('not')
    expect(facts.find((f) => f.key === 'official')?.status).toBe('not')
  })

  it('offer letter: a FAKE offer keeps Pathway red + a RED Official flag', () => {
    // not_offer_letter (p<0.35 — not recognisably a proper offer, e.g. #84 the private-uni
    // letter) → Official is RED. Pathway stays red (no pathway established).
    const d = doc({ doc_type: 'offer_letter',
      pathway_check: pathCheck({ name: 'match', ic: 'match', pathway: 'match' }),
      authenticity: { status: 'not_offer_letter', reason: 'few signatures' } })
    const facts = documentFacts(d)
    expect(facts.find((f) => f.key === 'pathway')?.status).toBe('not')
    expect(facts.find((f) => f.key === 'official')?.status).toBe('not')
    expect(documentPill(d)).toBe('check')
  })

  // ── IC-NUMBER chain (Item D): a wrong card in the slot, but the earner verified elsewhere ──
  it('parent_ic: wrong_card surfaces an amber caveat instead of the relationship label', () => {
    // #9: father's IC in the mother slot, but the chain verified the mother from the BC + STR.
    const facts = documentFacts(doc({ doc_type: 'parent_ic',
      income_ic_check: icCheck({ member: 'mother', readable: true, name_status: 'match',
                                 chain_verified: true, wrong_card: true }) }))
    expect(facts).toEqual([
      { key: 'name', status: 'verified' },     // the card is still legible
      { key: 'ic_no', status: 'verified' },
      { key: 'wrong_card', status: 'partial' },  // …but it's a different family member's
    ])
  })

  it('parent_ic: chain-verified with the RIGHT card shows no wrong-card caveat', () => {
    expect(documentFacts(doc({ doc_type: 'parent_ic',
      income_ic_check: icCheck({ member: 'mother', readable: true, name_status: 'match',
                                 chain_verified: true, wrong_card: false }) })).map((f) => f.key))
      .toEqual(['name', 'ic_no'])
  })

  // ── Proof chips (Item C): EPF/salary show IC No when the proof carries one ──
  it('epf chips: Name + IC No + Contribution + Balance + Current (from the EPF points)', () => {
    expect(documentFacts(doc({ doc_type: 'epf',
      income_proof_check: { name: 'X', nric: '750721-04-5130', name_status: 'match', nric_status: 'match',
        member: 'mother', ic_present: true, points: [
          { key: 'avgContribution', value: '300.00' },
          { key: 'totalAccumulated', value: '98730.34' },
          { key: 'statementDate', value: '2026' }] } })))
      .toEqual([{ key: 'name', status: 'verified' }, { key: 'ic_no', status: 'verified' },
                { key: 'contribution', status: 'verified' }, { key: 'balance', status: 'verified' },
                { key: 'current', status: 'verified' }])
  })

  it('epf chips stay present (grey) when a field was not read — consistent set', () => {
    const facts = documentFacts(doc({ doc_type: 'epf',
      income_proof_check: { name: 'X', nric: '750721-04-5130', name_status: 'match', nric_status: 'match',
        member: 'mother', ic_present: true, points: [] } }))
    expect(facts.map((f) => f.key)).toEqual(['name', 'ic_no', 'contribution', 'balance', 'current'])
    expect(facts.filter((f) => ['contribution', 'balance', 'current'].includes(f.key))
      .every((f) => f.status === 'unknown')).toBe(true)
  })

  it('salary slip: Amount + Period ALWAYS shown (grey when not read) — consistent 4-chip set', () => {
    const facts = (pts: { key: string; value: string }[]) => documentFacts(doc({ doc_type: 'salary_slip',
      income_proof_check: { name: 'X', nric: '', name_status: 'match', nric_status: 'no_ref',
        member: 'father', ic_present: true, points: pts } }))
    expect(facts([{ key: 'amount', value: '2000' }, { key: 'period', value: 'Apr 2026' }]).map((f) => f.key))
      .toEqual(['name', 'amount', 'period'])
    const noAmt = facts([{ key: 'period', value: 'Apr 2026' }])   // an EPF-in-the-slot has no amount
    expect(noAmt.map((f) => f.key)).toEqual(['name', 'amount', 'period'])  // amount not dropped
    expect(noAmt.find((f) => f.key === 'amount')!.status).toBe('unknown')  // …shown grey instead
  })

  it('genuineness gate: an IC flagged not_ic (WRONG TYPE) reads RED with a Wrong-type chip', () => {
    // an EPF uploaded into the IC slot — the scorer says not_ic (wrong document); its reads are off
    // the wrong paper → red, and the chip is 'wrongType' (red), never a green "Verified".
    const icFacts = documentFacts(doc({ doc_type: 'ic', vision_name_verdict: 'match', vision_nric_verdict: 'match',
      authenticity: { status: 'not_ic', reason: 'EPF statement, not a MyKad' } }))
    expect(icFacts).toEqual([
      { key: 'name', status: 'not' }, { key: 'ic_no', status: 'not' }, { key: 'wrongType', status: 'not' }])
    const parentFacts = documentFacts(doc({ doc_type: 'parent_ic',
      income_ic_check: icCheck({ member: 'father', name_status: 'match', readable: true }),
      authenticity: { status: 'not_ic', reason: 'EPF, not MyKad' } }))
    expect(parentFacts.map((f) => f.key)).toEqual(['name', 'ic_no', 'wrongType'])
    expect(parentFacts.every((f) => f.status === 'not')).toBe(true)
  })

  it('a SUSPECT IC keeps its Name/IC reads + an AMBER Genuine chip (suspect never caps)', () => {
    // A cropped-but-real MyKad: the name/IC that matched still read green; only the Genuine chip is
    // amber "we aren't sure". (The identity VERDICT still caps at Unsure — that is a separate signal.)
    const facts = documentFacts(doc({ doc_type: 'ic', vision_name_verdict: 'match', vision_nric_verdict: 'match',
      authenticity: { status: 'suspect', reason: 'glare / cropped' } }))
    expect(facts).toEqual([
      { key: 'name', status: 'verified' }, { key: 'ic_no', status: 'verified' },
      { key: 'genuine', status: 'partial' }])
  })

  // ── genuineness tone (owner 2026-07-07): WRONG-TYPE (red) caps the reads; SUSPECT (amber) never does ──
  it('a salary slip the wrong-type backstop reads as an EPF → RED reads + Wrong type chip', () => {
    const facts = documentFacts(doc({ doc_type: 'salary_slip',
      income_proof_check: { name: 'X', nric: '', name_status: 'match', nric_status: 'no_ref',
        member: 'father', ic_present: true, points: [{ key: 'amount', value: '300' }] },
      authenticity: { status: 'not_salary_slip', reason: 'reads as an epf' } }))
    expect(facts.find((f) => f.key === 'name')!.status).toBe('not')   // earner read is off the wrong paper
    expect(facts).toContainEqual({ key: 'wrongType', status: 'not' })
  })

  it('6-extend: an EPF flagged not_epf → RED reads + Wrong type chip (even the value chips do not green)', () => {
    const facts = documentFacts(doc({ doc_type: 'epf',
      income_proof_check: { name: 'X', nric: '750721-04-5130', name_status: 'match', nric_status: 'match',
        member: 'mother', ic_present: true, points: [] },
      authenticity: { status: 'not_epf', reason: 'withdrawal form' } }))
    expect(facts.find((f) => f.key === 'name')!.status).toBe('not')
    expect(facts.find((f) => f.key === 'ic_no')!.status).toBe('not')
    expect(facts).toContainEqual({ key: 'wrongType', status: 'not' })
  })

  it('a SUSPECT STR keeps its variable chips + an AMBER Genuine chip (suspect never caps)', () => {
    const facts = documentFacts(doc({ doc_type: 'str',
      str_check: strCheck({ name_status: 'match', nric_status: 'match', current_status: 'current' }),
      authenticity: { status: 'suspect', reason: 'thin signatures' } }))
    expect(facts.find((f) => f.key === 'recipient')!.status).toBe('verified')
    expect(facts.find((f) => f.key === 'status')!.status).toBe('verified')
    expect(facts).toContainEqual({ key: 'genuine', status: 'partial' })
    expect(facts.some((f) => f.status === 'not')).toBe(false)   // suspect reds NOTHING
  })

  it('a SUSPECT results slip keeps the academic reads (green) + an AMBER Genuine chip', () => {
    // #121: values are all there and match — the reviewer sees them stand; only genuineness is amber
    // ("we aren't sure the slip is genuine", usually a cropped footer). Missing reads would be grey.
    const facts = documentFacts(doc({ doc_type: 'results_slip',
      academic_check: acadCheck({ name: 'match', subjects: 'match', results: 'match' }),
      authenticity: { status: 'suspect', reason: 'cropped footer — QR/Pengarah missing' } }))
    expect(facts.filter((f) => ['name', 'subjects', 'results'].includes(f.key))
      .every((f) => f.status === 'verified')).toBe(true)
    expect(facts).toContainEqual({ key: 'genuine', status: 'partial' })
  })

  it('a WRONG-TYPE results slip DOES cap the reads red + a Wrong-type chip', () => {
    const facts = documentFacts(doc({ doc_type: 'results_slip',
      academic_check: acadCheck({ name: 'match', subjects: 'match', results: 'match' }),
      authenticity: { status: 'not_results_slip', reason: 'this is an offer letter' } }))
    expect(facts.filter((f) => ['name', 'subjects', 'results'].includes(f.key))
      .every((f) => f.status === 'not')).toBe(true)
    expect(facts).toContainEqual({ key: 'wrongType', status: 'not' })
  })

  it('6-extend: a GENUINE authenticity adds no cap (normal chips stand)', () => {
    const facts = documentFacts(doc({ doc_type: 'epf',
      income_proof_check: { name: 'X', nric: '750721-04-5130', name_status: 'match', nric_status: 'match',
        member: 'mother', ic_present: true, points: [{ key: 'avgContribution', value: '300' }] },
      authenticity: { status: 'genuine', reason: '' } }))
    expect(facts.find((f) => f.key === 'name')!.status).toBe('verified')
    expect(facts.some((f) => f.key === 'wrongType' || f.key === 'genuine')).toBe(false)
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

// ── incomeSubSections (STR ROUTE / SALARY ROUTE / UTILITY) ─────────────────────
describe('incomeSubSections', () => {
  const ids = (slots: { doc: AdminApplicantDocument | null }[]) => slots.map((s) => s.doc?.id ?? null)

  it('salary route: STR hidden; SALARY has per-member required slots (placeholders); UTILITY the bills', () => {
    const fIc = doc({ id: 1, doc_type: 'parent_ic', household_member: 'father' })
    const water = doc({ id: 9, doc_type: 'water_bill' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_working_members: ['father', 'mother'] }, [fIc, water])
    expect(sub.str).toBeNull()
    expect(sub.salary.map((s) => [s.docType, s.member, s.doc?.id ?? null])).toEqual([
      ['salary_slip', 'father', null],   // spec order: salary slip → IC → EPF
      ['parent_ic', 'father', 1],
      ['salary_slip', 'mother', null],
      ['parent_ic', 'mother', null],
      ['birth_certificate', '', null],   // mother needs a BC
    ])
    expect(ids(sub.utility)).toEqual([9])
  })

  it('STR route with an STR doc: STR sub shows the cluster; SALARY holds supplementary salary docs', () => {
    // Worked example: STR mother (also a cleaner) + a security-guard father. STR letter +
    // mother IC + applicant BC → STR; the cleaner/guard payslips + father IC + EPFs → SALARY.
    const str = doc({ id: 1, doc_type: 'str', household_member: 'mother' })
    const mIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'mother' })
    const bc = doc({ id: 3, doc_type: 'birth_certificate', household_member: '' })
    const mSlip = doc({ id: 4, doc_type: 'salary_slip', household_member: 'mother' })
    const fSlip = doc({ id: 5, doc_type: 'salary_slip', household_member: 'father' })
    const fIc = doc({ id: 6, doc_type: 'parent_ic', household_member: 'father' })
    const mEpf = doc({ id: 7, doc_type: 'epf', household_member: 'mother' })
    const fEpf = doc({ id: 8, doc_type: 'epf', household_member: 'father' })
    const sub = incomeSubSections(
      { income_route: 'str', income_earner: 'mother' }, [str, mIc, bc, mSlip, fSlip, fIc, mEpf, fEpf])
    // STR cluster: STR proof + mother's IC + applicant BC.
    expect(sub.str?.map((s) => [s.docType, s.doc?.id ?? null])).toEqual([
      ['str', 1], ['parent_ic', 2], ['birth_certificate', 3]])
    // SALARY: everything else (both slips, father's IC, both EPFs) — the mother's IC + STR + BC
    // are NOT duplicated here.
    const salaryIds = ids(sub.salary)
    expect(salaryIds).toEqual(expect.arrayContaining([4, 5, 6, 7, 8]))
    expect(salaryIds).not.toContain(1)   // STR proof stays in STR
    expect(salaryIds).not.toContain(2)   // mother's IC stays in STR
    expect(salaryIds).not.toContain(3)   // applicant BC stays in STR
  })

  it('salary route, father STR while mother is the declared earner: STR files the FATHER IC, not the earner (#45)', () => {
    // #45: the family is on the salary route (mother the declared earner + a slip), but the STR is the
    // FATHER's. The STR sub must show the RECIPIENT's (father's) IC — keyed off the STR's own member
    // tag, not income_earner — while the mother's IC belongs to SALARY.
    const str = doc({ id: 1, doc_type: 'str', household_member: 'father' })
    const fIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'father' })
    const mIc = doc({ id: 3, doc_type: 'parent_ic', household_member: 'mother' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_earner: 'mother', income_working_members: ['father', 'mother'] },
      [str, fIc, mIc])
    const strIcSlot = sub.str?.find((s) => s.docType === 'parent_ic')
    expect(strIcSlot?.member).toBe('father')      // the STR recipient, not the declared earner
    expect(strIcSlot?.doc?.id).toBe(2)
    expect(ids(sub.str ?? [])).not.toContain(3)   // mother's IC is NOT in the STR cluster
    expect(ids(sub.salary)).toContain(3)          // …it belongs to SALARY
  })

  it('salary route: a BLANK-tagged STR resolved to its recipient (father) still files the FATHER IC under STR', () => {
    // Robustness: the STR carries no household_member but the backend name-resolves the recipient
    // (resolved_member=father). The STR parent keys off memberOf (resolved_member || tag), so the
    // filing is correct even when the tag is blank — no fall-back to income_earner.
    const str = doc({ id: 1, doc_type: 'str', household_member: '', resolved_member: 'father' })
    const fIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'father' })
    const mIc = doc({ id: 3, doc_type: 'parent_ic', household_member: 'mother' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_earner: 'mother', income_working_members: ['father', 'mother'] },
      [str, fIc, mIc])
    const strIcSlot = sub.str?.find((s) => s.docType === 'parent_ic')
    expect(strIcSlot?.member).toBe('father')
    expect(strIcSlot?.doc?.id).toBe(2)
    expect(ids(sub.salary)).toContain(3)          // mother's IC in SALARY
  })

  it('4a: STR route derives salary members from the docs present, showing ONLY present docs (supportive)', () => {
    // #80 shape: the STR mother is the earner; the FATHER also has payslips but was never listed as
    // a working member. His docs form a structured Father group — but because this is the STR route
    // his salary docs are SUPPORTIVE, so an absent Father's IC raises NO "Missing" placeholder; only
    // the present salary slip + EPF show. (owner 2026-07-05.)
    const str = doc({ id: 1, doc_type: 'str', household_member: 'mother' })
    const mIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'mother' })
    const fSlip = doc({ id: 5, doc_type: 'salary_slip', household_member: 'father' })
    const fEpf = doc({ id: 8, doc_type: 'epf', household_member: 'father' })
    const sub = incomeSubSections(
      { income_route: 'str', income_earner: 'mother', income_working_members: [] },
      [str, mIc, fSlip, fEpf])
    expect(sub.salary.map((s) => [s.docType, s.member, s.doc?.id ?? null])).toEqual([
      ['salary_slip', 'father', 5],
      ['epf', 'father', 8],             // no Father's-IC "Missing" row on the STR route
    ])
  })

  it('4a: a member with ONLY an IC is not pulled into SALARY as a false earner', () => {
    // A blank/father IC alone is not income evidence — it must NOT create a "Missing salary" group
    // (usually it is the STR parent's IC). It still lands in the catch-all so it is never hidden.
    const str = doc({ id: 1, doc_type: 'str', household_member: 'mother' })
    const mIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'mother' })
    const fIc = doc({ id: 6, doc_type: 'parent_ic', household_member: 'father' })
    const sub = incomeSubSections(
      { income_route: 'str', income_earner: 'mother', income_working_members: [] }, [str, mIc, fIc])
    // no salary_slip placeholder was raised for the father…
    expect(sub.salary.some((s) => s.docType === 'salary_slip')).toBe(false)
    // …but his IC is still visible (catch-all), never dropped.
    expect(ids(sub.salary)).toContain(6)
  })

  it('STR route without any STR doc → STR sub hidden; the payslip earner shows present-only (supportive)', () => {
    // No STR doc → STR sub hidden. The route is STR, so salary docs stay supportive: the mother's
    // present payslip shows with NO compulsory IC/BC "Missing" placeholders.
    const mSlip = doc({ id: 4, doc_type: 'salary_slip', household_member: 'mother' })
    const sub = incomeSubSections({ income_route: 'str', income_earner: 'mother' }, [mSlip])
    expect(sub.str).toBeNull()
    expect(sub.salary.map((s) => [s.docType, s.member, s.doc?.id ?? null])).toEqual([
      ['salary_slip', 'mother', 4],
    ])
  })

  it('SALARY route KEEPS compulsory "Missing" placeholders (salary docs ARE the proof there)', () => {
    // Contrast: on the salary route the same absent Father's IC is required → red placeholder stays.
    const fSlip = doc({ id: 5, doc_type: 'salary_slip', household_member: 'father' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_working_members: ['father'] }, [fSlip])
    expect(sub.salary.map((s) => [s.docType, s.doc?.id ?? null])).toEqual([
      ['salary_slip', 5],
      ['parent_ic', null],   // required on the salary route → Missing placeholder kept
    ])
  })

  it('#63: a VALID STR on the salary route makes salary docs supportive (no "Missing")', () => {
    // #63 is on the salary route but holds a genuine approved (Lulus, undated→unconfirmed) STR — the
    // STR proves B40, so the model must NOT demand the mother's salary slip with a red placeholder.
    const str = doc({ id: 1, doc_type: 'str', household_member: 'mother',
      str_check: strCheck({ current_status: 'unconfirmed' }), authenticity: { status: 'genuine', reason: '' } })
    const mIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'mother' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_working_members: ['father', 'mother'] }, [str, mIc])
    expect(sub.str).not.toBeNull()                                         // STR cluster still shows
    expect(sub.salary.some((s) => s.docType === 'salary_slip' && s.doc === null)).toBe(false)  // no Missing
  })

  it('a BREACHED STR (wrong_type) on the salary route → salary docs ARE required (Missing kept)', () => {
    // Contrast: a SALINAN/payslip in the STR slot is breached → the family falls into full salary docs.
    const str = doc({ id: 1, doc_type: 'str', household_member: 'mother',
      str_check: strCheck({ current_status: 'wrong_type' }) })
    const sub = incomeSubSections(
      { income_route: 'salary', income_working_members: ['father'] }, [str])
    expect(sub.salary.some((s) => s.docType === 'salary_slip' && s.doc === null)).toBe(true)  // Missing kept
  })

  it('#63 regression: a salary-route family WITH STR docs still shows them (never hidden)', () => {
    // #63 was mis-switched to the salary route while holding a valid current STR (mother, Lulus)
    // plus an officer-requested copy. The STR sub used to be gated to route==='str', and the
    // SALARY tail didn't sweep `str`, so both STR docs rendered nowhere — invisible to the officer.
    const str1 = doc({ id: 620, doc_type: 'str', household_member: 'mother' })
    const str2 = doc({ id: 1253, doc_type: 'str', household_member: 'mother' })  // officer-requested copy
    const mSlip = doc({ id: 1569, doc_type: 'salary_slip', household_member: 'mother' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_working_members: ['mother'] }, [str1, str2, mSlip])
    // Both STR docs are visible under the STR sub-section…
    expect(sub.str).not.toBeNull()
    expect(sub.str!.filter((s) => s.docType === 'str').map((s) => s.doc?.id)).toEqual([620, 1253])
    // …and NOT duplicated into SALARY; the salary slip still renders.
    expect(ids(sub.salary)).not.toContain(620)
    expect(ids(sub.salary)).not.toContain(1253)
    expect(ids(sub.salary)).toContain(1569)
  })

  it('#63 doc-driven: STR cluster = STR + parent IC + applicant BC; blank father IC resolves under SALARY; mother IC not repeated', () => {
    const str = doc({ id: 1253, doc_type: 'str', household_member: 'mother' })
    const mIc = doc({ id: 623, doc_type: 'parent_ic', household_member: 'mother' })
    const bc = doc({ id: 624, doc_type: 'birth_certificate', household_member: '' })
    // the father's IC was uploaded with a BLANK tag; the backend resolved it by name → father
    const fIc = doc({ id: 1571, doc_type: 'parent_ic', household_member: '', resolved_member: 'father' })
    const mSlip = doc({ id: 1569, doc_type: 'salary_slip', household_member: 'mother' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_working_members: ['mother', 'father'] },
      [str, mIc, bc, fIc, mSlip])
    // STR cluster (doc-driven, even though route=salary): STR proof + mother's IC + applicant's BC
    expect(sub.str?.map((s) => [s.docType, s.doc?.id ?? null])).toEqual([
      ['str', 1253], ['parent_ic', 623], ['birth_certificate', 624]])
    const salaryPairs = sub.salary.map((s) => [s.docType, s.member, s.doc?.id ?? null])
    expect(salaryPairs).toContainEqual(['parent_ic', 'father', 1571])          // blank IC resolved → father
    expect(salaryPairs).not.toContainEqual(['parent_ic', 'mother', 623])       // shared-IC: not repeated
    expect(salaryPairs).toContainEqual(['salary_slip', 'mother', 1569])        // mother also works
  })

  it('guardian STR earner: the guardianship letter sits directly below the guardian IC', () => {
    const str = doc({ id: 1, doc_type: 'str', household_member: 'guardian' })
    const gIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'guardian' })
    const letter = doc({ id: 3, doc_type: 'guardianship_letter', household_member: '' })
    const sub = incomeSubSections(
      { income_route: 'str', income_earner: 'guardian' }, [str, gIc, letter])
    // STR proof → guardian IC → guardianship letter (letter directly below the IC)
    expect(sub.str?.map((s) => s.docType)).toEqual(['str', 'parent_ic', 'guardianship_letter'])
  })

  it('guardian salary earner: the guardianship letter sits directly below the guardian IC', () => {
    const gIc = doc({ id: 1, doc_type: 'parent_ic', household_member: 'guardian' })
    const letter = doc({ id: 2, doc_type: 'guardianship_letter', household_member: '' })
    const gEpf = doc({ id: 3, doc_type: 'epf', household_member: 'guardian' })
    const sub = incomeSubSections(
      { income_route: 'salary', income_working_members: ['guardian'] }, [gIc, letter, gEpf])
    const types = sub.salary.map((s) => s.docType)
    // salary slip (placeholder) → IC → guardianship letter → EPF
    expect(types).toEqual(['salary_slip', 'parent_ic', 'guardianship_letter', 'epf'])
    const icAt = types.indexOf('parent_ic')
    expect(types[icAt + 1]).toBe('guardianship_letter')   // directly below the IC
  })

  it('invisible-doc guard: any unplaced income doc still lands in the catch-all tail', () => {
    // A guardianship letter with no matching working-member slot must not vanish.
    const gl = doc({ id: 42, doc_type: 'guardianship_letter', household_member: '' })
    const sub = incomeSubSections({ income_route: 'salary', income_working_members: [] }, [gl])
    expect(ids(sub.salary)).toContain(42)
  })

  it('prefers the exactly-tagged earner IC over a blank-tagged one (blank goes to SALARY)', () => {
    // #63 shape: mother is the STR earner (IC tagged 'mother'); a blank-tagged parent_ic is
    // actually the father's — it must NOT be pulled into the STR earner slot.
    const str = doc({ id: 1, doc_type: 'str', household_member: 'mother' })
    const mIc = doc({ id: 2, doc_type: 'parent_ic', household_member: 'mother' })
    const blankIc = doc({ id: 3, doc_type: 'parent_ic', household_member: '' })
    const sub = incomeSubSections(
      { income_route: 'str', income_earner: 'mother' }, [str, mIc, blankIc])
    expect(sub.str?.find((s) => s.docType === 'parent_ic')?.doc?.id).toBe(2)  // exact earner IC
    expect(ids(sub.salary)).toContain(3)                                      // blank IC → SALARY
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

// ── Officer-decision gates (lifted from page.tsx — TD audit 2026-06-14) ─────────

describe('isClearAccept', () => {
  const ok = { identity: 'pass', academic: 'pass', pathway: 'pass', income: 'pass' }
  it('true when identity passed, nothing failed, complete, and live', () => {
    expect(isClearAccept(ok, true, 'interviewing')).toBe(true)
  })
  it('false when identity is not pass', () => {
    expect(isClearAccept({ ...ok, identity: '' }, true, 'interviewing')).toBe(false)
  })
  it('false when any of academic/pathway/income failed', () => {
    expect(isClearAccept({ ...ok, income: 'fail' }, true, 'interviewing')).toBe(false)
  })
  it('false when profile is not complete', () => {
    expect(isClearAccept(ok, false, 'interviewing')).toBe(false)
  })
  it('false when status is not a live state', () => {
    expect(isClearAccept(ok, true, 'active')).toBe(false)
  })
  it('treats a review/unsure (non-fail) academic as still acceptable', () => {
    expect(isClearAccept({ ...ok, academic: '' }, true, 'shortlisted')).toBe(true)
  })
})

describe('isQueryingLocked', () => {
  it('locks once the interview is submitted, regardless of status', () => {
    expect(isQueryingLocked('shortlisted', 'submitted')).toBe(true)
  })
  it('locks on a terminal/decided status', () => {
    expect(isQueryingLocked('rejected', undefined)).toBe(true)
    expect(isQueryingLocked('recommended', 'draft')).toBe(true)
    expect(isQueryingLocked('maintenance', 'draft')).toBe(true)
  })
  it('open while still shortlisted with a draft (or no) interview', () => {
    expect(isQueryingLocked('shortlisted', 'draft')).toBe(false)
    expect(isQueryingLocked('profile_complete', undefined)).toBe(false)
  })
})

describe('isDecisionReady', () => {
  const all = { identity: 'pass', academic: 'fail', pathway: 'pass', income: 'pass' }
  it('true when interview submitted, all four facts pass/fail, and a reason is written', () => {
    expect(isDecisionReady('submitted', all, 'Solid case.')).toBe(true)
  })
  it('false until the interview is submitted', () => {
    expect(isDecisionReady('draft', all, 'Solid case.')).toBe(false)
  })
  it('false when a fact has no pass/fail yet', () => {
    expect(isDecisionReady('submitted', { ...all, pathway: '' }, 'reason')).toBe(false)
  })
  it('false when the reason is blank/whitespace', () => {
    expect(isDecisionReady('submitted', all, '   ')).toBe(false)
  })
})

describe('isApproveReady', () => {
  it('requires decisionReady AND an assistance amount', () => {
    expect(isApproveReady(true, true)).toBe(true)
    expect(isApproveReady(true, false)).toBe(false)
    expect(isApproveReady(false, true)).toBe(false)
  })
})

describe('verdictItemKey — STR-not-current resolves to a flat per-status key', () => {
  const item = (code: string, params: Record<string, string | number | string[]> = {}): AdminVerdictItem =>
    ({ code, params })
  it('maps str_not_current + status to the suffixed key (the custom t has no ICU select)', () => {
    expect(verdictItemKey(item('str_not_current', { status: 'wrong_type' }))).toBe('str_not_current_wrong_type')
    expect(verdictItemKey(item('str_not_current', { status: 'rejected' }))).toBe('str_not_current_rejected')
    expect(verdictItemKey(item('str_not_current', { status: 'stale' }))).toBe('str_not_current_stale')
    expect(verdictItemKey(item('str_not_current', { status: 'unreadable' }))).toBe('str_not_current_unreadable')
    expect(verdictItemKey(item('str_not_current', { status: 'unconfirmed' }))).toBe('str_not_current_unconfirmed')
  })
  it('defaults a status-less str_not_current to the approved-but-dateless (unconfirmed) copy', () => {
    expect(verdictItemKey(item('str_not_current'))).toBe('str_not_current_unconfirmed')
  })
  it('passes every other item code through unchanged', () => {
    expect(verdictItemKey(item('income_salary_probable', { amount: 4200 }))).toBe('income_salary_probable')
    expect(verdictItemKey(item('earner_ic_missing', { members: ['father'] }))).toBe('earner_ic_missing')
  })
})

describe('headerTimeline — the cockpit header lifecycle chips', () => {
  const src = (over: Partial<TimelineSource>): TimelineSource => ({
    status: 'submitted',
    submitted_at: '2026-01-01T00:00:00Z',
    recommended_at: '2026-02-01T00:00:00Z',
    awarded_at: '2026-03-01T00:00:00Z',
    active_at: '2026-04-01T00:00:00Z',
    maintenance_at: '2026-05-01T00:00:00Z',
    ...over,
  })

  it('returns null before recommendation (header keeps its default Submitted·Applied·Assigned line)', () => {
    for (const status of ['submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed', 'rejected']) {
      expect(headerTimeline(src({ status }))).toBeNull()
    }
  })

  it('shows Submitted·Recommended·Awarded once recommended (and while awarded)', () => {
    for (const status of ['recommended', 'awarded']) {
      const steps = headerTimeline(src({ status }))
      expect(steps?.map((s) => s.labelKey)).toEqual(['submitted', 'recommended', 'awarded'])
      expect(steps?.map((s) => s.at)).toEqual([
        '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z', '2026-03-01T00:00:00Z',
      ])
    }
  })

  it('pivots to Awarded·Active·Maintenance once active (and while maintenance/closed)', () => {
    for (const status of ['active', 'maintenance', 'closed']) {
      const steps = headerTimeline(src({ status }))
      expect(steps?.map((s) => s.labelKey)).toEqual(['awarded', 'active', 'maintenance'])
      expect(steps?.map((s) => s.at)).toEqual([
        '2026-03-01T00:00:00Z', '2026-04-01T00:00:00Z', '2026-05-01T00:00:00Z',
      ])
    }
  })

  it('leaves a not-yet-reached step pending (null date → the header renders "—")', () => {
    const steps = headerTimeline(src({ status: 'recommended', awarded_at: null }))
    expect(steps?.find((s) => s.labelKey === 'awarded')?.at).toBeNull()
  })
})
