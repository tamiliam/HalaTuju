/**
 * @jest-environment jsdom
 */
/**
 * Follow-up to the higher-results-owed fix (owner 2026-11-07, app 278). Synthetic data only.
 *
 *  - an upload she never declared is served `grades_status: 'not_compared'`: the drawer's Results chip
 *    is grey (never red) and the Type chip carries no tick;
 *  - the declare ask with her document already on file (`params.doc_on_file`, served) reads "Enter your
 *    … results", never "Enter and upload", on her card and on the cockpit's Check-2 line;
 *  - the cockpit's "Querying closed" line no longer contradicts an open higher-results ask;
 *  - a printed STPM subject the server cannot recognise has words in all three languages.
 */
import { render, screen } from '@testing-library/react'
import { OutstandingPanel } from './OutstandingPanel'
import { higherResultsFacts } from '@/lib/higherResultsFacts'
import { itemCopy, titleSourceFor } from '@/lib/actionCentre'
import type { AdminResolutionItem, AdminScholarshipDetail } from '@/lib/admin-api'
import type { HigherCheck } from '@/lib/api'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const lookup = (cat: unknown) => (key: string) => {
  const v = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], cat)
  return typeof v === 'string' ? v : key
}
const st = (s: string | undefined | null) => (s === 'match' ? 'verified' : s === 'mismatch' ? 'not'
  : s === 'pending' ? 'partial' : 'unknown') as 'verified' | 'partial' | 'not' | 'unknown'

const DECLARE = (params: AdminResolutionItem['params'] = {}): AdminResolutionItem => ({
  id: 9, fact: 'academic', code: 'higher_results_declare_requested', params, prompt: '', kind: 'doc',
  doc_type: 'higher_results', status: 'open', source: 'check2', resolution_text: '',
  created_at: '2026-11-07T04:46:00.000Z', resolved_at: null,
} as unknown as AdminResolutionItem)

const panel = (items: AdminResolutionItem[], lockReason: 'interview' | 'closed' | null = 'interview') => {
  const app = { status: 'interviewing', resolution_items: items, officer_requests: 'closed', query_sla: {} }
  const noop = () => {}
  return render(<OutstandingPanel app={app as unknown as AdminScholarshipDetail} t={lookup(en) as never}
    busy="" canWrite decisionReopened={false} queryingLocked lockReason={lockReason} infoNote=""
    setInfoNote={noop} doRaiseQuery={noop} doActionResolution={noop} reqCategory="" reqQualifier=""
    reqDocNote="" setReqDocNote={noop} reqResolved={null} onReqCategory={noop} onReqQualifier={noop}
    doRequestDoc={noop} requestError="" />)
}

describe('point 1 + 2: an undeclared upload compares nothing', () => {
  it('the Results chip is grey and the Type chip has no tick', () => {
    const chk = { name: 'match', kind_status: '', cgpa_status: 'pending', grades_status: 'not_compared' }
    const facts = higherResultsFacts(chk as unknown as HigherCheck, st)
    expect(facts.find((f) => f.key === 'results')?.status).toBe('unknown')
    expect(facts.find((f) => f.key === 'type')?.status).toBe('unknown')
    expect(facts.find((f) => f.key === 'cgpa')?.status).toBe('partial')    // CGPA unchanged: amber
  })
})

describe('point 3: the declare ask once her document is on file', () => {
  it.each([[en, 'Enter your STPM'], [ms, 'Isi keputusan STPM'], [ta, 'பதிவுசெய்யவும்']])('%#: enter only, no upload', (cat, start) => {
    const t = lookup(cat)
    const src = titleSourceFor(DECLARE({ doc_on_file: true }))
    if (src.kind !== 'i18n') throw new Error('expected copy keys')
    const { title, desc } = itemCopy(t, src)
    expect(title).toContain(start)
    expect(title).not.toBe(t('scholarship.actionCentre.item.higher_results_declare_requested.title'))
    expect(desc).not.toBe(src.descKey)
  })
  it('without the flag it is the enter AND upload ask, as before', () => {
    const src = titleSourceFor(DECLARE())
    expect(src.kind === 'i18n' && src.titleKey).toBe('scholarship.actionCentre.item.higher_results_declare_requested.title')
  })
  it("the cockpit's Check-2 line says Enter, not Upload", () => {
    panel([DECLARE({ doc_on_file: true })])
    const line = screen.getByText(/Enter your STPM, Matriculation, Asasi or Diploma results/).closest('p')
    expect(line?.textContent).toMatch(/^Enter:/)
    expect(line?.textContent).not.toContain('Enter and upload')
  })
})

describe('point 4: the banner and an open late ask', () => {
  it('says the higher-results request is still open beside "Querying closed"', () => {
    panel([DECLARE()])
    const banner = screen.getByText(/Querying closed/)
    expect(banner.textContent).toContain(en.admin.scholarship.outstanding.lateAskOpen)
  })
  it('says nothing more when no such ask is open', () => {
    panel([{ ...DECLARE(), status: 'resolved' }])
    expect(screen.getByText(/Querying closed/).textContent).not.toContain(en.admin.scholarship.outstanding.lateAskOpen)
  })
  it('has words in all three languages', () => {
    for (const cat of [en, ms, ta]) {
      expect(cat.admin.scholarship.outstanding.lateAskOpen).toBeTruthy()
      expect(cat.admin.scholarship.outstanding.enterLabel).toBeTruthy()
      expect(cat.scholarship.actionCentre.item.higher_results_declare_requested.onFile.desc).toBeTruthy()
    }
  })
})

describe('point 6: an unrecognised STPM subject is named', () => {
  it('has words in all three languages', () => {
    for (const cat of [en, ms, ta]) {
      expect((cat.admin.scholarship.verdict.item as Record<string, string>).higher_results_subjects_unrecognised)
        .toContain('{subjects}')
    }
  })
})
