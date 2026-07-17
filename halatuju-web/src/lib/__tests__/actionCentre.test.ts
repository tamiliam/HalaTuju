import {
  iconFor,
  computeProgress,
  isOfficerItem,
  attributionFor,
  i18nKeyFor,
  titleSourceFor,
  confirmTargetFor,
  paramsToStrings,
  localiseParams,
  sortByWeight,
  clusterMemberOf,
  latestDocFor,
  needsOfficerEye,
  KNOWN_CODES,
  countDigits,
} from '@/lib/actionCentre'
import type { ResolutionItem } from '@/lib/api'
import en from '@/messages/en.json'

describe('attributionFor', () => {
  it('a known system/Check-2 code is "From our review assistant"', () => {
    expect(attributionFor({ source: 'system', code: 'birth_cert_missing' })).toBe('assistant')
    expect(attributionFor({ source: 'check2', code: 'transport_cost_unknown' })).toBe('assistant')
    expect(attributionFor({ source: 'system', code: 'pathway_confirm' })).toBe('assistant')
  })

  it('an officer (free-text / unknown code) item is "From your reviewer"', () => {
    expect(attributionFor({ source: 'officer', code: 'officer_1' })).toBe('reviewer')
    expect(attributionFor({ source: 'system', code: 'some_unknown_code' })).toBe('reviewer')
  })
})

// Minimal ticket factory — only the fields the pure helpers read.
function item(over: Partial<ResolutionItem> = {}): ResolutionItem {
  return {
    id: 1,
    fact: 'identity',
    code: 'ic_missing',
    params: {},
    prompt: '',
    kind: 'doc',
    doc_type: 'ic',
    status: 'open',
    source: 'system',
    resolution_text: '',
    created_at: '',
    resolved_at: null,
    ...over,
  }
}

describe('iconFor', () => {
  it('maps each kind to its icon family', () => {
    expect(iconFor('doc')).toBe('document')
    expect(iconFor('explanation')).toBe('chat')
    expect(iconFor('clarify')).toBe('chat')
    expect(iconFor('confirm')).toBe('checklist')
  })
})

describe('sortByWeight', () => {
  it('puts document blockers first and soft clarify questions last', () => {
    const items = [
      item({ id: 1, kind: 'clarify', code: 'sibling_level_unknown' }),
      item({ id: 2, kind: 'doc', code: 'birth_cert_missing' }),
      item({ id: 3, kind: 'confirm', code: 'nric_mismatch' }),
    ]
    expect(sortByWeight(items).map((i) => i.id)).toEqual([2, 3, 1])
  })

  it('is stable within the same weight (preserves server order)', () => {
    const items = [
      item({ id: 10, kind: 'doc' }),
      item({ id: 11, kind: 'doc' }),
    ]
    expect(sortByWeight(items).map((i) => i.id)).toEqual([10, 11])
  })
})

describe('computeProgress', () => {
  it('is 100% complete when nothing was ever raised', () => {
    expect(computeProgress([], [])).toEqual({ done: 0, total: 0, pct: 100 })
  })

  it('counts resolved as done and open+resolved as total', () => {
    const open = [item(), item({ id: 2 })]
    const resolved = [item({ id: 3, status: 'resolved' })]
    expect(computeProgress(open, resolved)).toEqual({ done: 1, total: 3, pct: 33 })
  })

  it('rounds the percentage to a whole number', () => {
    const open = [item()]
    const resolved = [item({ id: 2 }), item({ id: 3 })]
    // 2 of 3 done -> 66.67 -> 67
    expect(computeProgress(open, resolved).pct).toBe(67)
  })

  it('is 100% when all tickets are resolved', () => {
    const resolved = [item({ id: 1 }), item({ id: 2 })]
    expect(computeProgress([], resolved)).toEqual({ done: 2, total: 2, pct: 100 })
  })
})

describe('isOfficerItem', () => {
  it('is true for officer-sourced tickets', () => {
    expect(isOfficerItem({ source: 'officer', code: 'officer_1' })).toBe(true)
  })

  it('is true for unknown system codes (defensive)', () => {
    expect(isOfficerItem({ source: 'system', code: 'brand_new_code' })).toBe(true)
  })

  it('is false for known system codes', () => {
    for (const code of KNOWN_CODES) {
      expect(isOfficerItem({ source: 'system', code })).toBe(false)
    }
  })
})

// Regression guard (owner 2026-07-08): a code with per-item i18n copy but NOT registered in
// KNOWN_CODES is silently treated as a free-text officer ticket — so the student sees a BLANK
// title/desc and the officer sees the raw code (electricity_bill_recheck showed as its own code).
// Every `scholarship.actionCentre.item.*` code MUST be a KNOWN_CODE, and vice versa, so new
// student-facing copy can never ship without its frontend registration.
describe('KNOWN_CODES ↔ actionCentre.item i18n parity', () => {
  const itemCodes = Object.keys(
    (en as { scholarship: { actionCentre: { item: Record<string, unknown> } } })
      .scholarship.actionCentre.item,
  )
  const known = new Set(KNOWN_CODES as readonly string[])

  it('every item copy code is registered in KNOWN_CODES (no blank-title tasks)', () => {
    const orphanCopy = itemCodes.filter((c) => !known.has(c))
    expect(orphanCopy).toEqual([])
  })

  it('every KNOWN_CODE has item copy (except the bank task, which renders its own component)', () => {
    const missingCopy = (KNOWN_CODES as readonly string[])
      .filter((c) => c !== 'bank_details_missing' && !itemCodes.includes(c))
    expect(missingCopy).toEqual([])
  })
})

describe('i18nKeyFor', () => {
  it('namespaces under scholarship.actionCentre.item', () => {
    expect(i18nKeyFor('ic_missing')).toBe('scholarship.actionCentre.item.ic_missing')
  })
})

describe('titleSourceFor', () => {
  it('returns raw prompt for officer tickets', () => {
    const src = titleSourceFor({ source: 'officer', code: 'officer_2', prompt: 'Please call us' })
    expect(src).toEqual({ kind: 'raw', text: 'Please call us' })
  })

  it('returns i18n title + desc keys for known system codes', () => {
    const src = titleSourceFor({ source: 'system', code: 'nric_mismatch', prompt: '' })
    expect(src).toEqual({
      kind: 'i18n',
      titleKey: 'scholarship.actionCentre.item.nric_mismatch.title',
      descKey: 'scholarship.actionCentre.item.nric_mismatch.desc',
    })
  })

  it('reuses the bank card title for the resolved bank-details task (not a raw blank prompt)', () => {
    const src = titleSourceFor({ source: 'system', code: 'bank_details_missing', prompt: '' })
    expect(src).toEqual({
      kind: 'i18n',
      titleKey: 'scholarship.actionCentre.bank.title',
      descKey: 'scholarship.actionCentre.bank.intro',
    })
  })
})

describe('bank-details task attribution', () => {
  it('is the review assistant, never "from your reviewer"', () => {
    // Regression: bank_details_missing was missing from KNOWN_CODES, so the resolved
    // Done card was mislabelled as a free-text officer ticket ("From your reviewer").
    expect(isOfficerItem({ source: 'system', code: 'bank_details_missing' })).toBe(false)
    expect(attributionFor({ source: 'system', code: 'bank_details_missing' })).toBe('assistant')
  })
})

describe('confirmTargetFor', () => {
  it('routes academic grade/subject facts to the grades editor', () => {
    expect(confirmTargetFor('academic_missing_subjects')).toBe('grades')
    expect(confirmTargetFor('academic_grade_mismatch')).toBe('grades')
  })

  it('routes the results SLIP (a document) to documents, not the grades editor', () => {
    expect(confirmTargetFor('results_slip_missing')).toBe('documents')
    expect(confirmTargetFor('results_slip_unreadable')).toBe('documents')
    expect(confirmTargetFor('results_slip_name_mismatch')).toBe('documents')
  })

  it('routes pathway/story facts to story', () => {
    expect(confirmTargetFor('pathway')).toBe('story')
  })

  it('routes identity / income / anything else to documents', () => {
    expect(confirmTargetFor('identity')).toBe('documents')
    expect(confirmTargetFor('income')).toBe('documents')
    expect(confirmTargetFor('')).toBe('documents')
  })
})

describe('paramsToStrings', () => {
  it('stringifies numeric params', () => {
    expect(paramsToStrings({ count: 3, name: 'Aisyah' })).toEqual({ count: '3', name: 'Aisyah' })
  })

  it('handles null/undefined', () => {
    expect(paramsToStrings(undefined)).toEqual({})
    expect(paramsToStrings(null)).toEqual({})
  })
})

describe('localiseParams', () => {
  // Fake translator: returns the member label after the last dot, capitalised.
  const t = (key: string) => {
    const m = key.split('.').pop() || ''
    return m.charAt(0).toUpperCase() + m.slice(1)
  }

  it('localises + joins the income `members` array', () => {
    expect(localiseParams({ members: ['father', 'brother'] }, t)).toEqual({ members: 'Father, Brother' })
  })

  it('a single-member STR gap renders one label', () => {
    expect(localiseParams({ members: ['mother'] }, t)).toEqual({ members: 'Mother' })
  })

  it('passes other params through as strings', () => {
    expect(localiseParams({ name: 'Aisyah', count: 2 }, t)).toEqual({ name: 'Aisyah', count: '2' })
  })

  it('renders pathway codes as display labels (TD-161 switch card)', () => {
    // declared_pathway / offer_pathway route through scholarship.actionCentre.pathwayName.<code>
    // so the card reads "STPM"/"PISMP", not the raw code.
    expect(localiseParams({ declared_pathway: 'stpm', offer_pathway: 'pismp' }, t))
      .toEqual({ declared_pathway: 'Stpm', offer_pathway: 'Pismp' })
  })

  it('handles null/undefined', () => {
    expect(localiseParams(undefined, t)).toEqual({})
    expect(localiseParams(null, t)).toEqual({})
  })
})

describe('needsOfficerEye (circuit-breaker escalation, Phase 4)', () => {
  it('true only when the flag is boolean-true', () => {
    expect(needsOfficerEye(item({ params: { needs_officer_eye: true } }))).toBe(true)
  })

  it('false for a normal open task (no flag)', () => {
    expect(needsOfficerEye(item())).toBe(false)
    expect(needsOfficerEye(item({ params: { attempts: 2 } }))).toBe(false)
  })

  it('false for a non-boolean or falsy value (never a truthy-string trap)', () => {
    // A JSON false round-trips as a boolean; a stray string must not read as escalated.
    expect(needsOfficerEye(item({ params: { needs_officer_eye: false } }))).toBe(false)
    expect(needsOfficerEye(item({ params: { needs_officer_eye: 'true' } }))).toBe(false)
  })
})

describe('countDigits (bank account-number floor, code-health S3 #9)', () => {
  it('counts digits across formatting', () => {
    expect(countDigits('1234567890')).toBe(10)
    expect(countDigits('12-3456 7890')).toBe(10)
  })
  it('flags a truncated OCR fragment (<5 digits) that the API would reject', () => {
    expect(countDigits('123')).toBe(3)
    expect(countDigits('12a4')).toBe(3)
    expect(countDigits('')).toBe(0)
  })
})

describe('clusterMemberOf (V6 income cluster coach key, audit #15)', () => {
  it('salary route: uses the per-person request tag from params', () => {
    expect(clusterMemberOf(
      item({ kind: 'doc', doc_type: 'salary_slip', params: { household_member: 'father' } }),
      'salary', '',
    )).toBe('father')
  })
  it('STR route with no member tag: falls back to the declared earner', () => {
    expect(clusterMemberOf(
      item({ kind: 'doc', doc_type: 'str', params: {} }),
      'str', 'mother',
    )).toBe('mother')
  })
  it('a params member wins over the STR earner', () => {
    expect(clusterMemberOf(
      item({ kind: 'doc', doc_type: 'birth_certificate', params: { household_member: 'guardian' } }),
      'str', 'mother',
    )).toBe('guardian')
  })
  it('a non-cluster doc type is not a cluster task', () => {
    expect(clusterMemberOf(
      item({ kind: 'doc', doc_type: 'results_slip', params: { household_member: 'father' } }),
      'salary', '',
    )).toBe('')
  })
  it('a non-doc kind is never a cluster task', () => {
    expect(clusterMemberOf(
      item({ kind: 'explanation', doc_type: 'str', params: { household_member: 'father' } }),
      'str', 'father',
    )).toBe('')
  })
  it('an unknown member value is rejected', () => {
    expect(clusterMemberOf(
      item({ kind: 'doc', doc_type: 'epf', params: { household_member: 'cousin' } }),
      'salary', '',
    )).toBe('')
  })
  it('salary route with no member and no STR earner yields none', () => {
    expect(clusterMemberOf(
      item({ kind: 'doc', doc_type: 'salary_slip', params: {} }),
      'salary', 'father',
    )).toBe('')
  })
})

describe('latestDocFor (V6 reload-persistent coach, audit #15a)', () => {
  const doc = (id: number, doc_type: string, uploaded_at: string) =>
    ({ id, doc_type, uploaded_at }) as unknown as import('@/lib/api').ApplicantDocument
  it('returns the most recently uploaded doc of the type', () => {
    const docs = [doc(1, 'results_slip', '2026-07-01T00:00:00Z'), doc(2, 'results_slip', '2026-07-03T00:00:00Z')]
    expect(latestDocFor(docs, 'results_slip')?.id).toBe(2)
  })
  it('ignores other doc types', () => {
    const docs = [doc(1, 'ic', '2026-07-05T00:00:00Z'), doc(2, 'results_slip', '2026-07-01T00:00:00Z')]
    expect(latestDocFor(docs, 'results_slip')?.id).toBe(2)
  })
  it('returns null when nothing matches', () => {
    expect(latestDocFor([doc(1, 'ic', '2026-07-01T00:00:00Z')], 'offer_letter')).toBeNull()
  })
})
