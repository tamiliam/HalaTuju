/**
 * Owner rulings 2026-11-17 — the Academic tile, display only. Subtitle: a real problem leads, else
 * "not checked yet". The tile's band (red unreadable beats amber other kind / no real proof beats
 * blue) is computed on the server since F2: its cases live in `tests/test_fact_bands.py`.
 */
import { factDetailItems, factSubtitleItem } from '@/lib/officerCockpit'
import type { FactBand } from '@/lib/officerCockpit'
import type { AdminVerdictFact } from '@/lib/admin-api'
import enMessages from '@/messages/en.json'

const items = (codes: string[]) => codes.map((code) => ({ code, params: {} }))
function academic(status: AdminVerdictFact['status'], evidence: string[], unresolved: string[] = []): AdminVerdictFact {
  return { fact: 'academic', status, evidence: items(evidence), unresolved: items(unresolved) }
}

describe('Academic tile subtitle', () => {
  const code = (f: AdminVerdictFact, band: FactBand = 'probable') => factSubtitleItem(f, band)?.code
  test('#745/#257: the not-checked line leads the positive lines', () => {
    expect(code(academic('review', ['name_ok', 'kind_ok', 'cgpa_ok', 'higher_results_not_checked']))).toBe('higher_results_not_checked')
  })
  test('a real unresolved problem still leads', () => {
    expect(code(academic('review', ['name_ok', 'higher_results_not_checked'], ['higher_results_kind_differs']))).toBe('higher_results_kind_differs')
  })
  test('no not-checked note: first evidence line as before; nothing: null', () => {
    expect(code(academic('review', ['name_ok']))).toBe('name_ok')
    expect(factSubtitleItem(academic('review', []), 'unsure')).toBeNull()
  })
  test('a Certain tile does not promote the not-checked note', () => {
    expect(code(academic('verified', ['name_ok', 'higher_results_not_checked']), 'certain')).toBe('name_ok')
    expect(code(academic('verified', ['name_ok', 'higher_results_not_checked']), 'unsure'))
      .toBe('higher_results_not_checked')
  })
  test('the owner sentence is the en text', () => {
    const t = (enMessages as any).admin.scholarship.verdict.item.higher_results_not_checked
    expect(t).toBe('Genuineness of higher results is NOT checked yet.')
  })
})

describe('Academic tile - detail list', () => {
  test('detail list: subtitle is unresolved[0] - it is not repeated, evidence[0] is shown', () => {
    const f = academic('review', ['name_ok', 'cgpa_ok'], ['higher_results_kind_differs', 'x_other'])
    const d = factDetailItems(f, 'unsure')
    expect(d.unresolved.map((i) => i.code)).toEqual(['x_other'])
    expect(d.evidence.map((i) => i.code)).toEqual(['name_ok', 'cgpa_ok'])
  })
  test('detail list: subtitle is the not-checked evidence line - everything else shows', () => {
    const f = academic('review', ['name_ok', 'higher_results_not_checked', 'cgpa_ok'])
    const d = factDetailItems(f, 'probable')
    expect(d.evidence.map((i) => i.code)).toEqual(['name_ok', 'cgpa_ok'])
    expect(d.unresolved).toEqual([])
  })
})
