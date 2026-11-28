/**
 * @jest-environment jsdom
 */
/**
 * Chip Sprint 2, Phase B (owner 2026-11-28): a bill's holder name and address, and its bill-vs-application
 * comparison, live ONLY in the opened document's Checks panel. The drawer row shows no name or address and
 * the amount once (the plain chip). All values below are invented.
 */
import { render } from '@testing-library/react'
import { DocumentsDrawer } from './DocumentsDrawer'
import DocChecksPanel from '@/components/DocChecksPanel'
import type { ViewerDoc } from '@/components/DocViewer'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import en from '@/messages/en.json'

const t = (key: string, params?: Record<string, string>) => {
  const v = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], en)
  let s = typeof v === 'string' ? v : key
  for (const [k, val] of Object.entries(params || {})) s = s.replace(`{${k}}`, val)
  return s
}
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t, locale: 'en' }) }))

const bill = (o: Record<string, unknown> = {}) => ({
  id: 5, doc_type: 'water_bill', household_member: '', original_filename: 'bill.pdf', storage_path: 'x',
  uploaded_at: '2026-10-30T00:00:00Z', superseded_at: null, download_url: 'https://example.test/bill.pdf', content_type: 'application/pdf',
  chips: [
    { key: 'name', status: 'not', state: 'red', student_action: 'none', reason: 'unrelated', kind: 'fact' },
    { key: 'date', status: 'partial', state: 'amber', student_action: 'none', reason: 'ageing', kind: 'fact' },
    { key: 'amount', status: 'unknown', state: 'grey', student_action: 'none', reason: 'read', kind: 'plain', value: '84.20' },
  ], chip_pill: 'problem',
  utility_check: { name: 'SAMPLE HOLDER', address: '1 JALAN CONTOH, TAMAN UJIAN', monthly_bill: '84.20', unpaid_balance: '12.00',
    address_status: 'found', current_status: 'ageing', bill_month: 'Aug 2026', reasonable_status: 'reasonable',
    reasonable_detail: 'water_only', outstanding_status: '', name_note: 'unrelated', ...o },
})
const app = (doc: unknown) => ({
  name: 'SAMPLE STUDENT', address: '2 JALAN LAIN', postal_code: '00000', city: 'KOTA UJIAN',
  father_name: 'SAMPLE FATHER', mother_name: '',
  other_family_members: [{ role: 'guardian', name: 'SAMPLE GUARDIAN', occupation: 'x' }],
  documents: [doc,
    { id: 9, doc_type: 'parent_ic', vision_name: 'SAMPLE PARENT', superseded_at: null },
    { id: 10, doc_type: 'parent_ic', vision_name: 'SAMPLE OLD PARENT', superseded_at: '2026-10-01T00:00:00Z' }],
  verdict: [],
}) as unknown as AdminScholarshipDetail

function open(doc: unknown) {
  let viewer: ViewerDoc | null = null
  const r = render(<DocumentsDrawer app={app(doc)} t={t as never} busy="" canWrite={false}
    setViewerDoc={(v) => { viewer = v }} doReRunVision={() => {}} />)
  return { r, click: () => { (r.container.querySelector('button[title]') as HTMLButtonElement).click(); return viewer as ViewerDoc | null } }
}

describe('the drawer row for a bill', () => {
  it('shows no holder name, no address, no state note, and the amount once', () => {
    const { r } = open(bill())
    const text = r.container.textContent || ''
    expect(text).not.toContain('SAMPLE HOLDER')
    expect(text).not.toContain('JALAN CONTOH')
    expect(text).not.toContain('Bill is in another name')
    expect(text).not.toContain('Water bill only')
    expect(text.split('84.20').length - 1).toBe(1)
  })
})

describe('the Checks panel for a bill', () => {
  it('shows the bill beside the application, the date rule and the plain values', () => {
    const { click } = open(bill())
    const doc = click()
    expect(doc?.checks?.bill).toBeTruthy()
    const { container } = render(<DocChecksPanel checks={doc!.checks!} />)
    const text = container.textContent || ''
    for (const s of ['SAMPLE HOLDER', 'SAMPLE STUDENT', 'SAMPLE FATHER', 'SAMPLE GUARDIAN', 'SAMPLE PARENT', '1 JALAN CONTOH',
      '2 JALAN LAIN, 00000, KOTA UJIAN', 'Aug 2026', 'Up to 3 months old is current', '84.20', 'Reasonable', 'Outstanding',
      'Bill is in another name: SAMPLE HOLDER', 'Water bill only', 'Bill is older than 3 months.']) {
      expect(text).toContain(s)
    }
  })

  it('lists the father, the roster and the live parent ICs as the application names, not a replaced IC', () => {
    const { click } = open(bill({ name: 'SAMPLE FATHER' }))
    const doc = click()
    const { container } = render(<DocChecksPanel checks={doc!.checks!} />)
    const text = container.textContent || ''
    expect(text).toContain('SAMPLE STUDENT · SAMPLE FATHER · SAMPLE GUARDIAN · SAMPLE PARENT')
    expect(text).not.toContain('SAMPLE OLD PARENT')
  })

  it('draws nothing of the kind for a document that is not a bill', () => {
    const { container } = render(<DocChecksPanel checks={{ chips: [], pill: 'unread', readAt: null }} />)
    expect(container.querySelector('[data-bill-checks]')).toBeNull()
  })
})
