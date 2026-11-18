/**
 * #804 (owner 2026-11-18): a red Pathway tile read "No pathway chosen yet" while the reason it was
 * red was the course start year. A confident disqualifier now leads the tile's subtitle, and the
 * FE list is pinned to the backend `award.CONFIDENT_DISQUALIFIERS` in both directions.
 */
import { CONFIDENT_DISQUALIFIERS, factDetailItems, factSubtitleItem } from '@/lib/officerCockpit'
import type { AdminVerdictFact } from '@/lib/admin-api'
import { pySeq, readApi } from '@/test/apiSource'

const AWARD = 'apps/scholarship/award.py'

function backendDisqualifiers(): string[] {
  return pySeq(readApi(AWARD), 'CONFIDENT_DISQUALIFIERS')
}

const items = (codes: string[]) => codes.map((code) => ({ code, params: {} }))
function pathway(status: AdminVerdictFact['status'], evidence: string[], unresolved: string[]): AdminVerdictFact {
  return { fact: 'pathway', status, evidence: items(evidence), unresolved: items(unresolved) }
}

describe('CONFIDENT_DISQUALIFIERS mirror', () => {
  test('the FE set equals the backend tuple', () => {
    const be = backendDisqualifiers()
    expect(be.length).toBeGreaterThanOrEqual(4)
    expect([...CONFIDENT_DISQUALIFIERS].sort()).toEqual([...be].sort())
  })
})

describe('tile subtitle - a confident disqualifier leads', () => {
  test('#804: the start year leads an earlier undeclared line', () => {
    const f = pathway('gap', ['offer_programme'], ['pathway_undeclared', 'pathway_start_year_outside'])
    expect(factSubtitleItem(f)?.code).toBe('pathway_start_year_outside')
    const d = factDetailItems(f)
    expect(d.unresolved.map((i) => i.code)).toEqual(['pathway_undeclared'])
    expect(d.evidence.map((i) => i.code)).toEqual(['offer_programme'])
  })
  test('the first disqualifier leads when there are two', () => {
    const f = pathway('gap', [], ['pathway_undeclared', 'pathway_funded_or_abroad', 'pathway_start_year_outside'])
    expect(factSubtitleItem(f)?.code).toBe('pathway_funded_or_abroad')
  })
  test('no disqualifier: the first unresolved line leads as before', () => {
    const f = pathway('review', ['offer_programme'], ['pathway_undeclared', 'offer_issuer_not_checked'])
    expect(factSubtitleItem(f)?.code).toBe('pathway_undeclared')
  })
})
