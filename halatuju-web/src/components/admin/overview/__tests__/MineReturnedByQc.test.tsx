/**
 * @jest-environment jsdom
 *
 * #86: the "Returned by QC" mark. It is the SERVED `returned_by_qc` flag, drawn on the My-open table (phone cards
 * and desktop table) and nowhere else by inference: true shows it, false or absent hides it. A decided case on My
 * open has no clock (null due date and band): it renders empty, never a crash.
 */
import { render, screen } from '@testing-library/react'

import en from '@/messages/en.json'
import ReturnedByQcMark from '@/components/admin/ReturnedByQcMark'
import type { ProgrammeOverview } from '@/lib/admin-api'
import { MineSection } from '../OverviewSections'

const lookup = (key: string): string | undefined =>
  key.split('.').reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), en) as string | undefined
const t = (key: string, params?: Record<string, string>): string => {
  const raw = lookup(key)
  if (typeof raw !== 'string') return key
  return raw.replace(/\{(\w+)\}/g, (_m, p: string) => params?.[p] ?? `{${p}}`)
}

jest.mock('@/lib/i18n', () => ({
  ...jest.requireActual('@/lib/i18n'),
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
}))

const row = (id: number, over: Record<string, unknown> = {}) => ({
  id, ref: `HT-${id}`, applicant_name: `Student ${id}`, status: 'interviewing',
  assigned_at: '2026-11-20T00:00:00Z', due_at: '2026-11-27T00:00:00Z', band: 'open', ...over,
})
const data = (cases: unknown[]) => ({
  programme: null, generated_at: '2026-11-27T00:00:00Z', data_to: null, sections: ['mine'], intake: null, intakes: [],
  mine: { open: cases.length, due_soon: 0, overdue: 0, cases, pace: { completed: 0, turnaround_days: null } },
}) as unknown as ProgrammeOverview

describe('Returned by QC mark', () => {
  it('shows when true, on the phone card and the desktop table', () => {
    render(<MineSection data={data([row(196, { returned_by_qc: true, due_at: null, band: null })])} t={t} />)
    expect(screen.getAllByText('Returned by QC')).toHaveLength(2)
  })

  it('is hidden when false or absent', () => {
    render(<MineSection data={data([row(1, { returned_by_qc: false }), row(2)])} t={t} />)
    expect(screen.queryByText('Returned by QC')).toBeNull()
  })

  it('renders a decided case with no due date or band without crashing', () => {
    const { container } = render(<MineSection data={data([row(513, { due_at: null, band: null })])} t={t} />)
    expect(screen.getAllByText(/HT-513/).length).toBeGreaterThan(0)
    expect(container.querySelector('[data-returned-by-qc]')).toBeNull()
    expect(screen.queryByText('admin.overview.band.null')).toBeNull()
  })

  it('the mark itself honours show', () => {
    const { container, rerender } = render(<ReturnedByQcMark show label="X" />)
    expect(container.querySelector('[data-returned-by-qc]')).not.toBeNull()
    rerender(<ReturnedByQcMark show={undefined} label="X" />)
    expect(container.querySelector('[data-returned-by-qc]')).toBeNull()
  })
})
