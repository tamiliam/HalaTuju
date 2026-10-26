/**
 * Third results route S4 — the reviewer's side (2026-10-27; #37, #43, D15).
 *
 *  - "Request a document" → Results slip offers the SPM slip and the higher results BY NAME, each
 *    resolving to `higher_results` with its kind (the server stores it; the upload lands there);
 *  - the Academic card's note for a higher result moved OUT of the SPM card, by the student or by
 *    the team (the 2026-10-26 backfill, `by: 'team'`);
 *  - the Documents drawer's fact line for a higher result in the SPM card: Name, and Type in red —
 *    never Subjects / Results, which were not compared.
 */
import { REQ_CAT, resolveReq, resultsChangeKey } from './shared'
import { slipHigherFacts } from '@/lib/higherResultsFacts'
import en from '@/messages/en.json'

describe('#37: results by name', () => {
  it('offers the SPM slip, each higher kind and the CGPA slip', () => {
    const values = REQ_CAT.get('results_slip')!.options!.map((o) => o.value)
    expect(values).toEqual(['spm', 'higher_stpm', 'higher_matric', 'higher_asasi', 'higher_diploma', 'cgpa'])
  })
  it.each([
    ['higher_stpm', 'stpm'], ['higher_matric', 'matric'], ['higher_asasi', 'asasi'], ['higher_diploma', 'diploma'],
  ])('%s resolves to higher_results with kind %s', (q, kind) => {
    expect(resolveReq('results_slip', q)).toEqual({ docType: 'higher_results', member: '', kind })
  })
  it('the SPM slip and the CGPA slip carry no kind, as before', () => {
    expect(resolveReq('results_slip', 'spm')).toEqual({ docType: 'results_slip', member: '' })
    expect(resolveReq('results_slip', 'cgpa')).toEqual({ docType: 'semester_result', member: '' })
    expect(resolveReq('results_slip', '')).toBeNull()
  })
  it('every new choice has its words and its standard request line', () => {
    const s = en.admin.scholarship as unknown as Record<string, Record<string, string>>
    for (const o of REQ_CAT.get('results_slip')!.options!) {
      expect(s.requestWhich[o.value]).toBeTruthy()
      if (o.kind) expect(s.requestDocStd[`higher_${o.kind}`]).toBeTruthy()
    }
    expect(s.requestRefused.results_kind_required).toBeTruthy()
  })
})

describe('D15: the Academic card names who moved a higher result out of the SPM card', () => {
  it.each([
    [{ kind: 'refiled_higher', by: 'student' }, 'admin.scholarship.resultsChanged.refiledHigher'],
    [{ kind: 'refiled_higher', by: 'team' }, 'admin.scholarship.resultsChanged.refiledHigherTeam'],
    [{ kind: 'refiled_spm' }, 'admin.scholarship.resultsChanged.refiledSpm'],
    [{ kind: 'only_spm', by: 'student' }, 'admin.scholarship.resultsChanged.onlySpm'],
  ])('%j → %s', (note, key) => {
    expect(resultsChangeKey(note)).toBe(key)
  })
  it('the team line reads as the brief asked', () => {
    expect(en.admin.scholarship.resultsChanged.refiledHigherTeam)
      .toBe('Moved from the SPM card to the {kind} results card by the HalaTuju team on {date}.')
  })
})

describe('#43: the drawer\'s facts for a higher result in the SPM card', () => {
  it('Name as read, Type red, and no Subjects / Results', () => {
    const facts = slipHigherFacts({ name: 'match' } as never, (s) => (s === 'match' ? 'verified' : 'unknown'))
    expect(facts).toEqual([{ key: 'name', status: 'verified' }, { key: 'type', status: 'not' }])
  })
})
