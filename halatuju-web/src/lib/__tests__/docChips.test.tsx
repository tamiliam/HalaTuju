/**
 * @jest-environment jsdom
 */
import { render, screen } from '@testing-library/react'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import { CHIP_SYMBOL, PILL_COLOURS, STATE_COLOURS, formatReadTime, kindToState, servedChip, type DocChipData } from '@/lib/docChips'
import { DocChip, DocPill } from '@/components/DocChip'
import DocChecksPanel from '@/components/DocChecksPanel'
import {
  ChipLine, NotesIcon, REASON_WORDS, ReadTime, ReasonLines, drawerChips, drawerPill, readTimeShows,
} from '../../app/admin/scholarship/[id]/view/docChipRow'
import { OfferLetterChecklist } from '@/components/ScholarshipDocuments/checklistsPathway'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => k.split('.').slice(-1)[0] + (p ? `|${Object.values(p).join(',')}` : '') }),
}))
const t = (k: string, p?: Record<string, string>) => k.split('.').slice(-1)[0] + (p ? `|${Object.values(p).join(',')}` : '')
const chip = (key: string, state: DocChipData['state'], extra: Partial<DocChipData> = {}): DocChipData =>
  ({ key, status: 'unknown', state, student_action: 'none', reason: '', kind: 'fact', ...extra })

describe('the one colour map', () => {
  test('symbols: green tick, amber bang, red cross, grey none', () => {
    expect(CHIP_SYMBOL).toEqual({ green: '✓', amber: '!', red: '✕', grey: '' })
  })
  test.each([
    ['green', 'positive'], ['amber', 'caution'], ['red', 'critical'],
  ] as const)('%s chip uses the %s tokens', (state, tone) => {
    expect(STATE_COLOURS[state].chip).toContain(tone)
  })
  test('the Problem pill is red and Check is amber', () => {
    expect(PILL_COLOURS.problem).toContain('critical')
    expect(PILL_COLOURS.check).toContain('caution')
  })
  test('both student greys are one grey', () => {
    expect(kindToState('unreadable' as never)).toBe('grey')
    expect(kindToState('none' as never)).toBe('grey')
  })
})

describe('DocChip and DocPill', () => {
  test.each([['green', '✓'], ['amber', '!'], ['red', '✕']] as const)('%s draws %s', (state, sym) => {
    render(<DocChip state={state}>Name</DocChip>)
    expect(document.querySelector(`[data-chip="${state}"]`)?.textContent).toBe(`${sym}Name${state}`)   // the last part is the sr-only state word (the mock t echoes the key tail)
  })
  test('grey has no symbol', () => {
    render(<DocChip state="grey">IC No</DocChip>)
    expect(document.querySelector('[data-chip="grey"]')?.textContent).toBe('IC Nogrey')
  })
  test('every chip says its state in words for a screen reader, in one sr-only span', () => {
    render(<DocChip state="amber">Name</DocChip>)
    const w = document.querySelector('[data-chip="amber"] [data-chip-state]') as HTMLElement
    expect(w.className).toContain('sr-only')
    expect(w.textContent).toBe('amber')
    expect(document.querySelectorAll('[data-chip-state]').length).toBe(1)
  })
  test('a plain value is the value only, with no ring', () => {
    render(<DocChip state="grey" plain>RM 2,350</DocChip>)
    const el = document.querySelector('[data-chip="plain"]') as HTMLElement
    expect(el.textContent).toBe('RM 2,350')
    expect(el.className).not.toContain('ring-')
  })
  test('the pill carries its word', () => {
    render(<DocPill pill="problem">Problem</DocPill>)
    expect(document.querySelector('[data-pill="problem"]')?.textContent).toBe('Problem')
  })
})

describe('read time', () => {
  const now = new Date(2026, 10, 28, 12, 0)
  test('this year has no year', () => expect(formatReadTime(new Date(2026, 10, 25, 9, 12).toISOString(), { now })).toBe('25 Nov, 09:12'))
  test('another year shows the year', () => expect(formatReadTime(new Date(2025, 10, 25, 9, 12).toISOString(), { now })).toBe('25 Nov 2025, 09:12'))
  test('full always shows the year', () => expect(formatReadTime(new Date(2026, 10, 25, 9, 12).toISOString(), { now, full: true })).toBe('25 Nov 2026, 09:12'))
  test('null and junk give nothing', () => {
    expect(formatReadTime(null)).toBe('')
    expect(formatReadTime('nope')).toBe('')
  })
  test('the drawer says not read yet when read_at is null', () => {
    render(<ReadTime readAt={null} t={t} />)
    expect(screen.getByText('readAtNone')).toBeTruthy()
  })
  test('nothing is shown when read_at is absent (an old payload) or does not parse', () => {
    expect(render(<ReadTime readAt={undefined} t={t} />).container.innerHTML).toBe('')
    expect(render(<ReadTime readAt="nope" t={t} />).container.innerHTML).toBe('')
  })
  test('the read time does not wrap', () => {
    render(<ReadTime readAt={new Date(2026, 10, 25, 9, 12).toISOString()} t={t} now={new Date(2026, 10, 28)} />)
    expect((document.querySelector('[data-read-at]') as HTMLElement).className).toContain('whitespace-nowrap')
  })
  test('the month follows the language', () => {
    const iso = new Date(2026, 10, 25, 9, 12).toISOString()
    const now = new Date(2026, 10, 28)
    expect(formatReadTime(iso, { now, locale: 'ms' })).toMatch(/25 Nov.*09:12/)
    const ta = formatReadTime(iso, { now, locale: 'ta' })
    expect(ta).not.toContain('Nov')
    expect(ta).toContain('09:12')
  })
})

describe('the drawer draws the served chips and falls back without them', () => {
  const served = { id: 1, doc_type: 'ic', chips: [chip('name', 'red'), chip('ic_no', 'grey')], chip_pill: 'problem' } as unknown as AdminApplicantDocument
  test('served chips and pill win', () => {
    expect(drawerChips(served).map((c) => c.state)).toEqual(['red', 'grey'])
    expect(drawerPill(served)).toBe('problem')
    render(<ChipLine chips={drawerChips(served)} t={t} />)
    expect(document.querySelectorAll('[data-chip="red"]').length).toBe(1)
    expect(document.querySelectorAll('[data-chip="grey"]').length).toBe(1)
  })
  test('a payload with no chips uses the old functions', () => {
    const old = { id: 2, doc_type: 'ic' } as unknown as AdminApplicantDocument
    expect(Array.isArray(drawerChips(old))).toBe(true)
    expect(drawerPill(old)).not.toBe('problem')
  })
  test('an EMPTY served chip list (the server chip code failed) falls back, for the chips and the pill', () => {
    const failed = { id: 3, doc_type: 'ic', chips: [], chip_pill: 'unread', vision_run_at: '2026-11-01T00:00:00Z' } as unknown as AdminApplicantDocument
    expect(drawerChips(failed)).not.toBe(failed.chips)
    expect(drawerPill(failed)).toBe(drawerPill({ id: 3, doc_type: 'ic', vision_run_at: '2026-11-01T00:00:00Z' } as unknown as AdminApplicantDocument))
  })
  test('servedChip falls back on an empty chip list too', () => {
    expect(servedChip({ chips: [] }, 'name')).toBeUndefined()
  })
  test('servedChip finds a fact chip by key only', () => {
    expect(servedChip({ chips: [chip('name', 'green'), chip('name', 'amber', { kind: 'year' })] }, 'name')?.state).toBe('green')
    expect(servedChip({}, 'name')).toBeUndefined()
  })
})

describe('the shells', () => {
  test('no reason line while no fixed words exist', () => {
    expect(Object.keys(REASON_WORDS)).toHaveLength(0)
    const { container } = render(<ReasonLines chips={[chip('name', 'red', { reason: 'mismatch' })]} t={t} />)
    expect(container.innerHTML).toBe('')
  })
  test('the notes icon is hidden without a count', () => {
    const { container } = render(<NotesIcon count={undefined} t={t} />)
    expect(container.innerHTML).toBe('')
  })
  test('the Checks panel lists each chip with the full times', () => {
    render(<DocChecksPanel checks={{ chips: [chip('name', 'red'), chip('ic_no', 'amber')], pill: 'problem',
      readAt: new Date(2025, 10, 25, 9, 12).toISOString(), uploadedAt: new Date(2025, 10, 24, 21, 40).toISOString() }} />)
    expect(document.body.textContent).toContain('25 Nov 2025, 09:12')
    expect(document.body.textContent).toContain('24 Nov 2025, 21:40')
  })
  test('the Checks panel says so when empty and never read', () => {
    render(<DocChecksPanel checks={{ chips: [], pill: 'unread', readAt: null, uploadedAt: null }} />)
    expect(screen.getByText('empty')).toBeTruthy()
    expect(screen.getByText('readAtNone')).toBeTruthy()
  })
  test('the Checks panel says the state through the translated word (one span, inside the chip) and nothing for an old payload', () => {
    render(<DocChecksPanel checks={{ chips: [chip('name', 'red')], pill: 'problem', readAt: undefined }} />)
    expect(document.querySelector('[data-check="red"] [data-chip-state]')?.textContent).toBe('red')   // mock echoes the key tail
    expect(screen.queryByText('readAtNone')).toBeNull()
  })
  test('the Checks panel scrolls on a phone', () => {
    render(<DocChecksPanel checks={{ chips: [], pill: 'unread', readAt: null }} />)
    expect((document.querySelector('[data-checks-panel]') as HTMLElement).className).toContain('max-md:max-h-[40dvh]')
  })
})

describe('round 2 review fixes', () => {
  test('a student chip (spoken false) has no sr-only word; an officer field chip has one', () => {
    const { container } = render(<><DocChip state="green" spoken={false}>Match</DocChip><DocChip state="green">Name</DocChip></>)
    const chips = container.querySelectorAll('[data-chip]')
    expect(chips[0].querySelector('[data-chip-state]')).toBeNull()
    expect(chips[1].querySelector('[data-chip-state]')).not.toBeNull()
  })
  test('an officer year chip says its state (its text has no state word)', () => {
    render(<ChipLine chips={[chip('examYear', 'amber', { kind: 'year', value: 2025 }), chip('name', 'green')]} t={t} />)
    const all = document.querySelectorAll('[data-chip]')
    expect(all[0].querySelector('[data-chip-state]')?.textContent).toBe('amber')
    expect(all[1].querySelector('[data-chip-state]')).not.toBeNull()
  })
  test('the fallback pill reads Problem when a drawn fact chip is red', () => {
    const d = { id: 3, doc_type: 'ic', chips: [], vision_name_verdict: 'mismatch' } as unknown as AdminApplicantDocument
    expect(drawerChips(d).some((c) => c.kind === 'fact' && c.state === 'red')).toBe(true)
    expect(drawerPill(d)).toBe('problem')
  })
  test('the separator before the read time shows only when the time shows', () => {
    expect(readTimeShows(undefined)).toBe(false)
    expect(readTimeShows('nope')).toBe(false)
    expect(readTimeShows(null)).toBe(true)
    expect(readTimeShows(new Date(2026, 10, 25, 9, 12).toISOString())).toBe(true)
  })
  test('the Tamil date has no double comma, with or without the year', () => {
    const iso = new Date(2025, 10, 25, 9, 12).toISOString()
    const withYear = formatReadTime(iso, { now: new Date(2026, 10, 28), locale: 'ta' })
    const noYear = formatReadTime(iso, { now: new Date(2025, 10, 28), locale: 'ta' })
    expect(withYear).not.toMatch(/,\s*,/)
    expect(withYear).toMatch(/2025, 09:12$/)
    expect(noYear).toMatch(/09:12$/)
    expect(withYear).not.toMatch(/\.,\s*2025/)
  })
  test('the Tamil chip words', () => {
    const ta = require('@/messages/ta.json')
    expect(ta.common.chipState.amber).toBe('சரிபார்க்க வேண்டும்')
    expect(ta.admin.scholarship.docsDrawer.notesHint).toContain('ஆவணத்தைத் திறக்கவும்')
  })
})

describe('round 3 review fixes', () => {
  test('student offer chips: a result word is not spoken; the field-name-only IC chip (not printed) is', () => {
    const doc = { id: 9, doc_type: 'offer_letter', pathway_check: {
      name: 'match', ic: 'not_printed', candidate_name: '', candidate_nric: '', programme: '', institution: '',
      issuer: '', offer_date: '', intake: '', address: '' } } as unknown as Parameters<typeof OfferLetterChecklist>[0]['doc']
    const { container } = render(<OfferLetterChecklist doc={doc} t={(k: string) => k.split('.').slice(-1)[0]} />)
    const chips = container.querySelectorAll('[data-chip]')
    expect(chips[0].textContent).toBe('✓match')   // aria-hidden symbol + the result word, nothing more
    expect(chips[0].querySelector('[data-chip-state]')).toBeNull()
    expect(chips[1].querySelector('[data-chip-state]')?.textContent).toBe('grey')
  })
  test('the served IC chip (label pathwayCheck.ic) draws its label and speaks its state', () => {
    const doc = { id: 10, doc_type: 'offer_letter',
      chips: [chip('ic', 'grey', { reason: 'not_printed', label: 'scholarship.docs.pathwayCheck.ic' })],
      pathway_check: {
        name: 'match', ic: 'not_printed', candidate_name: '', candidate_nric: '', programme: '', institution: '',
        issuer: '', offer_date: '', intake: '', address: '' } } as unknown as Parameters<typeof OfferLetterChecklist>[0]['doc']
    const { container } = render(<OfferLetterChecklist doc={doc} t={(k: string) => k.split('.').slice(-1)[0]} />)
    const icChip = container.querySelectorAll('[data-chip]')[1]
    expect(icChip.getAttribute('data-chip')).toBe('grey')
    expect(icChip.textContent).toBe('icgrey')   // the served label + the spoken state word; grey has no symbol
  })
})
