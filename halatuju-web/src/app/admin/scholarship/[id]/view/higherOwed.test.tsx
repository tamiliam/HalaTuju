/**
 * @jest-environment jsdom
 */
/**
 * Higher results OWED over a pre-S3 frozen snapshot (2026-10-27; owner option A, application #388).
 *
 *  - the Documents drawer draws the "STPM results" slot as MISSING from the SERVED Academic fact
 *    (`higher_results_not_on_file`, or S3's `higher_results_missing`) — never re-derived here;
 *  - the team's own notes (its refiles, its split of a combined upload) are no longer drawn (owner
 *    2026-11-06: not served, `results_route.cockpit_notes`); the student's still are;
 *  - the student's Check-2 ask reads "Please upload your STPM results" in her language.
 */
import { render, screen } from '@testing-library/react'
import { DocumentsDrawer } from './DocumentsDrawer'
import { missingHigherKind, resultsChangeKey } from './shared'
import { KNOWN_CODES, localiseParams, onboardingAskFor } from '@/lib/actionCentre'
import type { AdminScholarshipDetail, AdminVerdictFact } from '@/lib/admin-api'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const lookup = (cat: unknown) => (key: string) => {
  const v = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], cat)
  return typeof v === 'string' ? v : key
}
const academic = (code: string, params: Record<string, string> = {}): AdminVerdictFact =>
  ({ fact: 'academic', status: 'review', evidence: [], unresolved: [{ code, params }] })

describe('#388: the missing higher-results slot is read off the served Academic fact', () => {
  it('names the kind held when owed over a pre-S3 snapshot', () => {
    expect(missingHigherKind({ verdict: [academic('higher_results_not_on_file', { held: 'STPM', kind: 'stpm' })] }))
      .toBe('stpm')
  })
  it("S3's own missing upload shows the slot too, with no kind", () => {
    expect(missingHigherKind({ verdict: [academic('higher_results_missing')] })).toBe('')
  })
  it('nothing missing → null, and another fact never counts', () => {
    expect(missingHigherKind({ verdict: [academic('grades_verified')] })).toBeNull()
    expect(missingHigherKind({ verdict: [{ ...academic('higher_results_not_on_file'), fact: 'income' }] })).toBeNull()
    expect(missingHigherKind({ verdict: [] as AdminVerdictFact[] })).toBeNull()
  })
  it('the drawer renders the Missing row under Academic, even with no academic document', () => {
    const app = { documents: [], verdict: [academic('higher_results_not_on_file', { held: 'STPM', kind: 'stpm' })] }
    const t = lookup(en)
    render(<DocumentsDrawer app={app as unknown as AdminScholarshipDetail} t={t as never} busy=""
      setViewerDoc={() => {}} doReRunVision={() => {}} />)
    const row = screen.getByTestId('higher-missing')
    expect(row.textContent).toContain('STPM results')
    expect(row.textContent).toContain(en.admin.scholarship.docsDrawer.pill.missing)
  })
  it('and no Missing row when the verdict says nothing is owed', () => {
    const app = { documents: [], verdict: [academic('grades_verified')] }
    render(<DocumentsDrawer app={app as unknown as AdminScholarshipDetail} t={lookup(en) as never} busy=""
      setViewerDoc={() => {}} doReRunVision={() => {}} />)
    expect(screen.queryByTestId('higher-missing')).toBeNull()
  })
})

describe("the Academic card draws the student's notes only (owner 2026-11-06)", () => {
  it.each([
    [{ kind: 'refiled_higher', by: 'student' }, 'admin.scholarship.resultsChanged.refiledHigher'],
    [{ kind: 'refiled_spm' }, 'admin.scholarship.resultsChanged.refiledSpm'],
    [{ kind: 'only_spm' }, 'admin.scholarship.resultsChanged.onlySpm'],
    [{ kind: 'team_split' }, null],
  ])('%j → %s', (note, key) => {
    expect(resultsChangeKey(note)).toBe(key)
  })
  it("the team's lines are gone from all three languages", () => {
    for (const cat of [en, ms, ta]) {
      const rc = cat.admin.scholarship.resultsChanged as Record<string, unknown>
      for (const k of ['refiledHigherTeam', 'refiledHigherTeamSemester', 'refiledSpmTeam', 'teamSplitSpm', 'teamSplitHigher']) {
        expect(rc[k]).toBeUndefined()
      }
      expect(rc.refiledHigher).toContain('{kind}')
    }
  })
})

describe("the student's Check-2 ask", () => {
  it('is a known code with words in all three languages', () => {
    expect(KNOWN_CODES).toContain('higher_results_requested')
    for (const cat of [en, ms, ta]) {
      expect(cat.scholarship.actionCentre.item.higher_results_requested.title).toContain('{kind}')
      expect(cat.admin.scholarship.verdict.item.higher_results_not_on_file).toContain('{held}')
    }
  })
  it.each([[en, 'STPM'], [ms, 'Matrikulasi']])('the kind reads as its word', (cat, word) => {
    const kind = cat === en ? 'stpm' : 'matric'
    const out = localiseParams({ results_kind: kind }, lookup(cat))
    expect(out.kind).toBe(word)
    expect(lookup(cat)('scholarship.actionCentre.item.higher_results_requested.title').replace('{kind}', out.kind))
      .toBe(cat === en ? 'Please upload your final STPM results' : 'Sila muat naik keputusan akhir Matrikulasi anda')   // M4b: only the final result counts
  })
})

describe('2026-11-07: declared SPM only, bound for a degree (apps 158 / 168 / 247)', () => {
  it('the served `higher_results_not_declared` draws the generic Missing slot (all four named)', () => {
    expect(missingHigherKind({ verdict: [academic('higher_results_not_declared', { kind: '' })] })).toBe('')
    const app = { documents: [], verdict: [academic('higher_results_not_declared', { kind: '' })] }
    render(<DocumentsDrawer app={app as unknown as AdminScholarshipDetail} t={lookup(en) as never} busy=""
      setViewerDoc={() => {}} doReRunVision={() => {}} />)
    expect(screen.getByTestId('higher-missing').textContent)
      .toContain('STPM / Matriculation / Asasi / Diploma results')
  })
  it('the undeclared-on-file reason is not a Missing slot', () => {
    expect(missingHigherKind({ verdict: [academic('higher_results_undeclared')] })).toBeNull()
  })
  it('the declare + upload ask is a known code with words in all three languages and an onboarding button', () => {
    expect(KNOWN_CODES).toContain('higher_results_declare_requested')
    expect(onboardingAskFor('higher_results_declare_requested'))
      .toEqual({ path: '/onboarding/exam-type', buttonKey: 'scholarship.actionCentre.enterHigherResults' })
    for (const cat of [en, ms, ta]) {
      const item = cat.scholarship.actionCentre.item.higher_results_declare_requested
      expect(item.title).toContain('STPM')
      expect(item.desc).toContain('SPM')
      expect(item.title).not.toContain('{kind}')
      expect(cat.scholarship.actionCentre.enterHigherResults).toBeTruthy()
    }
    expect(en.scholarship.actionCentre.item.higher_results_declare_requested.title)
      .toBe('Enter and upload your STPM, Matriculation, Asasi or Diploma results')
  })
  it('both reasons have words in all three languages', () => {
    for (const cat of [en, ms, ta]) {
      const items = cat.admin.scholarship.verdict.item as Record<string, string>
      expect(items.higher_results_not_declared).toBeTruthy()
      expect(items.higher_results_undeclared).toBeTruthy()
    }
  })
})
