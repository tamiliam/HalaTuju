/**
 * Owner rulings 2026-11-17 — the Academic tile, display only. Tone: red (unreadable) beats amber
 * (other kind / no real proof) beats blue. Subtitle: a real problem leads, else "not checked yet".
 */
import { factDetailItems, factSubtitleItem, factTileTone } from '@/lib/officerCockpit'
import type { AdminVerdictFact } from '@/lib/admin-api'
import enMessages from '@/messages/en.json'

const items = (codes: string[]) => codes.map((code) => ({ code, params: {} }))
function academic(status: AdminVerdictFact['status'], evidence: string[], unresolved: string[] = []): AdminVerdictFact {
  return { fact: 'academic', status, evidence: items(evidence), unresolved: items(unresolved) }
}

describe('Academic tile tone', () => {
  test('#548: only the not-checked note as evidence is not proof, and unreadable is red', () => {
    expect(factTileTone(academic('review', ['higher_results_not_checked']))).toBe('amber')
    expect(factTileTone(academic('review', ['higher_results_not_checked'], ['higher_results_unreadable']))).toBe('red')
  })
  test('unreadable is red even when other evidence would make it blue', () => {
    expect(factTileTone(academic('review', ['name_ok', 'higher_results_not_checked'], ['higher_results_unreadable']))).toBe('red')
  })
  test('#170: kind differs caps at amber even with a matching name', () => {
    expect(factTileTone(academic('review', ['name_ok', 'higher_results_not_checked'], ['higher_results_kind_differs']))).toBe('amber')
    expect(factTileTone(academic('review', ['name_ok'], ['higher_results_is_spm']))).toBe('amber')
  })
  test('#745/#257: real proof plus not-checked, nothing unresolved, stays blue', () => {
    expect(factTileTone(academic('review', ['name_ok', 'kind_ok', 'cgpa_ok', 'higher_results_not_checked']))).toBe('blue')
  })
  test('a verified tile stays green', () => {
    expect(factTileTone(academic('verified', ['name_ok']))).toBe('green')
  })
})

describe('Academic tile subtitle', () => {
  const code = (f: AdminVerdictFact) => factSubtitleItem(f)?.code
  test('#745/#257: the not-checked line leads the positive lines', () => {
    expect(code(academic('review', ['name_ok', 'kind_ok', 'cgpa_ok', 'higher_results_not_checked']))).toBe('higher_results_not_checked')
  })
  test('a real unresolved problem still leads', () => {
    expect(code(academic('review', ['name_ok', 'higher_results_not_checked'], ['higher_results_kind_differs']))).toBe('higher_results_kind_differs')
  })
  test('no not-checked note: first evidence line as before; nothing: null', () => {
    expect(code(academic('review', ['name_ok']))).toBe('name_ok')
    expect(factSubtitleItem(academic('review', []))).toBeNull()
  })
  test('the owner sentence is the en text', () => {
    const t = (enMessages as any).admin.scholarship.verdict.item.higher_results_not_checked
    expect(t).toBe('Genuineness of higher results is NOT checked yet.')
  })
})

describe('Academic tile - status interplay and detail list', () => {
  test('verified + unreadable is red; verified + kind differs is amber; gap stays red', () => {
    expect(factTileTone(academic('verified', ['name_ok'], ['higher_results_unreadable']))).toBe('red')
    expect(factTileTone(academic('verified', ['name_ok'], ['higher_results_kind_differs']))).toBe('amber')
    expect(factTileTone(academic('gap', []))).toBe('red')
  })
  test('detail list: subtitle is unresolved[0] - it is not repeated, evidence[0] is shown', () => {
    const f = academic('review', ['name_ok', 'cgpa_ok'], ['higher_results_kind_differs', 'x_other'])
    const d = factDetailItems(f)
    expect(d.unresolved.map((i) => i.code)).toEqual(['x_other'])
    expect(d.evidence.map((i) => i.code)).toEqual(['name_ok', 'cgpa_ok'])
  })
  test('detail list: subtitle is the not-checked evidence line - everything else shows', () => {
    const f = academic('review', ['name_ok', 'higher_results_not_checked', 'cgpa_ok'])
    const d = factDetailItems(f)
    expect(d.evidence.map((i) => i.code)).toEqual(['name_ok', 'cgpa_ok'])
    expect(d.unresolved).toEqual([])
  })
})
