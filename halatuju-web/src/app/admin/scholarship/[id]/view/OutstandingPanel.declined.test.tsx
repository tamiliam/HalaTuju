/**
 * @jest-environment jsdom
 *
 * H7: the reviewer sees the reason (and note) a student gave for "I don't have this". Synthetic data.
 */
import { render, screen } from '@testing-library/react'
import { OutstandingPanel } from './OutstandingPanel'
import type { AdminResolutionItem, AdminScholarshipDetail } from '@/lib/admin-api'
import en from '@/messages/en.json'

const t = (key: string) => {
  const v = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], en)
  return typeof v === 'string' ? v : key
}

const ITEM = (params: Record<string, unknown>): AdminResolutionItem => ({
  id: 4, fact: 'income', code: 'electricity_bill_recheck', params, prompt: '', kind: 'doc', doc_type: 'electricity_bill',
  status: 'resolved', resolved_by: 'student', source: 'check2', resolution_text: '',
  created_at: '2026-11-07T04:46:00.000Z', resolved_at: '2026-11-08T04:46:00.000Z',
} as unknown as AdminResolutionItem)

const panel = (item: AdminResolutionItem) => {
  const app = { status: 'interviewing', resolution_items: [item], officer_requests: 'closed', query_sla: {} }
  const noop = () => {}
  return render(<OutstandingPanel app={app as unknown as AdminScholarshipDetail} t={t as never}
    busy="" canWrite decisionReopened={false} queryingLocked={false} lockReason={null} infoNote=""
    setInfoNote={noop} doRaiseQuery={noop} doActionResolution={noop} reqCategory="" reqQualifier=""
    reqDocNote="" setReqDocNote={noop} reqResolved={null} onReqCategory={noop} onReqQualifier={noop}
    doRequestDoc={noop} requestError="" />)
}

describe('a declined optional ask on the reviewer panel', () => {
  it('shows the label and the reason', () => {
    panel(ITEM({ declined_reason: 'landlord_pays' }))
    expect(screen.getByText('Student does not have this')).toBeTruthy()
    expect(screen.getByText(/landlord pays it/i)).toBeTruthy()
  })

  it('shows the note after "Other"', () => {
    panel(ITEM({ declined_reason: 'other', declined_note: 'We rent a room.' }))
    expect(screen.getByText(/We rent a room\./)).toBeTruthy()
  })

  it('shows nothing extra when nothing was declined', () => {
    panel(ITEM({}))
    expect(screen.queryByText('Student does not have this')).toBeNull()
  })
})
