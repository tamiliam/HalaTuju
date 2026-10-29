/**
 * The engineer's analysis on the Requests screens (owner, 2026-10-05): the badge, the list tag,
 * and the approve wording. Every key these helpers return must exist in en / ms / ta.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import {
  analysisBadge, analysisBadgeKey, analysisBadgeTone, listAnalysisTag, listAnalysisTagKey,
  analysisApproveKind, analysisApproveCopy, hoursAnalysisId, type AnalysisBadge,
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

describe('which analysis carries the hours panel', () => {
  /** ⚠ ONE PLACE (owner, 2026-10-30). The panel was on every approved, un-superseded card, and
   *  request #3 has two: after the figures were recorded on the one the invoice reads, the other
   *  went on saying "No hours recorded yet — the invoice for this month will refuse until they
   *  are". That was FALSE, and it asked for the same work twice. */
  const a = (id: number, over: Record<string, unknown> = {}) => ({
    id, approved_at: `2026-10-0${id}T00:00:00Z`, superseded_at: null,
    charged_hours: null, ...over,
  })

  it('picks the analysis the INVOICE reads — the latest one CARRYING a figure', () => {
    // Request #3, exactly: id 14 holds 3.5/3.5, id 15 is a later approved note with no figures.
    const rows = [a(4, { charged_hours: '3.5' }), a(5)]
    expect(hoursAnalysisId(rows)).toBe(4)
  })

  it('falls to the newest approved analysis while nothing is recorded anywhere', () => {
    expect(hoursAnalysisId([a(4), a(5)])).toBe(5)
  })

  it('ignores a draft and a superseded analysis', () => {
    const draftRow = { ...a(9), approved_at: null }
    const supersededRow = a(8, { superseded_at: '2026-10-09T00:00:00Z', charged_hours: '2.0' })
    expect(hoursAnalysisId([a(4), draftRow, supersededRow])).toBe(4)
  })

  it('treats a recorded ZERO as a figure, because "none of it is charged" is an answer', () => {
    expect(hoursAnalysisId([a(4, { charged_hours: '0.0' }), a(5)])).toBe(4)
  })

  it('compares ids as NUMBERS when two share an approval time', () => {
    // ⚠ `[x, y] > [p, q]` coerces to strings in JavaScript, which puts 9 after 10.
    const same = '2026-10-01T00:00:00Z'
    const rows = [{ ...a(9), approved_at: same }, { ...a(10), approved_at: same }]
    expect(hoursAnalysisId(rows)).toBe(10)
  })

  it('says NOTHING to write to when no analysis is approved', () => {
    expect(hoursAnalysisId([{ ...a(1), approved_at: null }])).toBeNull()
    expect(hoursAnalysisId([])).toBeNull()
  })
})
