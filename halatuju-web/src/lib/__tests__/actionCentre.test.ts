import {
  iconFor,
  computeProgress,
  isOfficerItem,
  i18nKeyFor,
  titleSourceFor,
  confirmTargetFor,
  paramsToStrings,
  localiseParams,
  KNOWN_CODES,
} from '@/lib/actionCentre'
import type { ResolutionItem } from '@/lib/api'

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
    expect(iconFor('confirm')).toBe('checklist')
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
})

describe('confirmTargetFor', () => {
  it('routes academic facts to results', () => {
    expect(confirmTargetFor('academic')).toBe('results')
    expect(confirmTargetFor('results_grade')).toBe('results')
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

  it('handles null/undefined', () => {
    expect(localiseParams(undefined, t)).toEqual({})
    expect(localiseParams(null, t)).toEqual({})
  })
})
