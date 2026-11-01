/**
 * @jest-environment jsdom
 */
/**
 * Route-aware exam-year colours (owner rule, 2026-11-01): the Documents drawer tints the STPM year of
 * a higher-results document from the SERVED `higher_check.exam_year_status` — 'current' green, 'off'
 * amber — exactly as it tints the SPM year of a results slip. The colour is decided on the server
 * (`exam_years`); the drawer never computes it.
 */
import { render, screen } from '@testing-library/react'
import { DocumentsDrawer } from './DocumentsDrawer'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import en from '@/messages/en.json'

const t = (key: string, params?: Record<string, string>) => {
  const v = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], en)
  let s = typeof v === 'string' ? v : key
  for (const [k, val] of Object.entries(params || {})) s = s.replace(`{${k}}`, val)
  return s
}

const higherDoc = (exam_year: string, exam_year_status: string) => ({
  id: 7, doc_type: 'higher_results', household_member: '', original_filename: 'stpm.pdf', storage_path: 'x',
  uploaded_at: '2026-10-30T00:00:00Z', superseded_at: null, results_kind: 'stpm',
  higher_check: {
    name: 'match', candidate_name: '', exam: 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA', kind_held: 'stpm',
    kind_detected: 'stpm', kind_status: 'match', cgpa_slip: null, cgpa_entered: null, cgpa_status: 'pending',
    grades_status: '', missing: [], mismatched: [], readable: true, note: '', note_kind: '', note_path: '',
    exam_year, exam_year_status,
  },
})

const draw = (doc: unknown) => render(
  <DocumentsDrawer app={{ documents: [doc], verdict: [] } as unknown as AdminScholarshipDetail}
    t={t as never} busy="" setViewerDoc={() => {}} doReRunVision={() => {}} />)

describe('the STPM year chip', () => {
  it('an off-route year is amber', () => {
    draw(higherDoc('2022', 'off'))
    expect(screen.getByText('STPM 2022').className).toContain('text-caution-700')
  })
  it('the expected year is green', () => {
    draw(higherDoc('2025', 'current'))
    expect(screen.getByText('STPM 2025').className).toContain('text-positive-700')
  })
  it('no year, no chip', () => {
    draw(higherDoc('', ''))
    expect(screen.queryByText(/^STPM \d{4}$/)).toBeNull()
  })
})
