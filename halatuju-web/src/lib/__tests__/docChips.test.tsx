/**
 * @jest-environment jsdom
 */
import { render, screen } from '@testing-library/react'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import { CHIP_SYMBOL, PILL_COLOURS, STATE_COLOURS, formatReadTime, kindToState, servedChip, type DocChipData } from '@/lib/docChips'
import { DocChip, DocPill } from '@/components/DocChip'
import DocChecksPanel from '@/components/DocChecksPanel'
import {
  ChipLine, NotesIcon, REASON_WORDS, ReadTime, ReasonLines, drawerChips, drawerPill,
} from '../../app/admin/scholarship/[id]/view/docChipRow'

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
    expect(document.querySelector(`[data-chip="${state}"]`)?.textContent).toBe(`${sym}Name`)
  })
  test('grey has no symbol', () => {
    render(<DocChip state="grey">IC No</DocChip>)
    expect(document.querySelector('[data-chip="grey"]')?.textContent).toBe('IC No')
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
})
