/**
 * The engineer's analysis on the Requests screens (owner, 2026-10-05): the badge, the list tag,
 * and the approve wording. Every key these helpers return must exist in en / ms / ta.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import {
  analysisBadge, analysisBadgeKey, analysisBadgeTone, listAnalysisTag, listAnalysisTagKey,
  analysisApproveKind, analysisApproveCopy, type AnalysisBadge,
} from '@/lib/requestStatus'

const T = '2026-10-05T00:00:00Z'
const draft = { approved_at: null, superseded_at: null }
const withdrawn = { approved_at: null, superseded_at: T }
const approved = { approved_at: T, superseded_at: null }
const superseded = { approved_at: T, superseded_at: T }

function has(locale: unknown, key: string): boolean {
  return typeof key.split('.').reduce<unknown>(
    (o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), locale,
  ) === 'string'
}

describe('analysisBadge', () => {
  it('names each of the four states', () => {
    expect(analysisBadge(draft)).toBe('draft')
    expect(analysisBadge(withdrawn)).toBe('withdrawn')
    expect(analysisBadge(approved)).toBe('approved')
    expect(analysisBadge(superseded)).toBe('superseded')
  })

  it('a withdrawn draft never reads "Awaiting your approval" (request #26)', () => {
    expect(analysisBadgeKey(analysisBadge(withdrawn))).not.toBe(analysisBadgeKey('draft'))
    expect(analysisBadgeTone('withdrawn')).toContain('ground')
  })

  it('every badge key exists in en / ms / ta', () => {
    for (const b of ['draft', 'withdrawn', 'approved', 'superseded'] as AnalysisBadge[]) {
      for (const loc of [en, ms, ta]) expect(has(loc, analysisBadgeKey(b))).toBe(true)
    }
  })
})

describe('listAnalysisTag', () => {
  it('tags a submitted request by its live analysis', () => {
    expect(listAnalysisTag('submitted', [draft])).toBe('analysisDraft')
    expect(listAnalysisTag('submitted', [withdrawn, approved])).toBe('analysed')
  })

  it('a withdrawn draft alone does not count', () => {
    expect(listAnalysisTag('submitted', [withdrawn])).toBeNull()
  })

  it('no tag past submitted, with no analysis, or for the org (no analyses in its payload)', () => {
    expect(listAnalysisTag('quoted', [approved])).toBeNull()
    expect(listAnalysisTag('submitted', [])).toBeNull()
    expect(listAnalysisTag('submitted', undefined)).toBeNull()
  })

  it('both tag keys exist in en / ms / ta', () => {
    for (const tag of ['analysed', 'analysisDraft'] as const) {
      for (const loc of [en, ms, ta]) expect(has(loc, listAnalysisTagKey(tag))).toBe(true)
    }
  })
})

describe('analysisApproveKind', () => {
  it("the engineer's reading wins over the requester's type (request #30)", () => {
    expect(analysisApproveKind({ ...draft, proposed_kind: 'feature' }, { kind: 'bug' })).toBe('feature')
    expect(analysisApproveKind({ ...draft, proposed_kind: 'bug' }, { kind: 'feature' })).toBe('bug')
  })

  it('falls back to the triage, then to the requester', () => {
    expect(analysisApproveKind(draft, { kind: 'feature', triaged_kind: 'bug' })).toBe('bug')
    expect(analysisApproveKind({ ...draft, proposed_kind: '' }, { kind: 'bug', triaged_kind: '' })).toBe('bug')
    expect(analysisApproveKind(draft, { kind: 'feature' })).toBe('feature')
  })

  it('a bug and a feature get different wording, and every key exists', () => {
    expect(analysisApproveCopy('bug').label).not.toBe(analysisApproveCopy('feature').label)
    for (const kind of ['bug', 'feature'] as const) {
      for (const key of Object.values(analysisApproveCopy(kind))) {
        for (const loc of [en, ms, ta]) expect(has(loc, key)).toBe(true)
      }
    }
  })
})
