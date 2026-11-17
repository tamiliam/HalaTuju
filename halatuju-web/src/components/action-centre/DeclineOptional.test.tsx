/**
 * @jest-environment jsdom
 *
 * H7: "I don't have this" on an optional ask. Reasons show only after the tap; a reason tap sends at
 * once; "Other" needs words before Send works; Cancel goes back to Upload; a required ask has no button.
 */
import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { DeclineOptional } from './DeclineOptional'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  declineResolutionItem: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))

const mockApi = api as jest.Mocked<typeof api>
const ITEM: ResolutionItem = {
  id: 7, fact: 'income', code: 'water_bill_recheck', params: {}, prompt: '', kind: 'doc', doc_type: 'water_bill',
  status: 'open', source: 'check2', resolution_text: '', created_at: '2026-11-01T09:00:00.000Z', resolved_at: null,
  decline_reasons: ['no_water_bill', 'landlord_pays', 'other'],
} as unknown as ResolutionItem

const Host = ({ item = ITEM, onDone = () => {} }: { item?: ResolutionItem; onDone?: () => void }) => {
  const [open, setOpen] = useState(false)
  return <DeclineOptional item={item} token="tkn" open={open} onOpen={() => setOpen(true)} onCancel={() => setOpen(false)} onDone={onDone} />
}
const P = 'documentsTab.actionCentre.decline.'
// The reasons ride the Documents slice too (second bundle trim); the admin panel has its own copy.
const R = P

beforeEach(() => { jest.clearAllMocks(); mockApi.declineResolutionItem.mockResolvedValue({} as never) })

describe('DeclineOptional', () => {
  it('shows only the button until it is tapped, then the reasons', () => {
    render(<Host />)
    expect(screen.queryByText(`${R}reasons.water_bill.landlord_pays`)).toBeNull()
    fireEvent.click(screen.getByText(`${P}button`))
    expect(screen.getByText(`${P}ask`)).toBeTruthy()
    expect(screen.getByText(`${R}reasons.water_bill.landlord_pays`)).toBeTruthy()
  })

  it('Cancel goes back to the button', () => {
    render(<Host />)
    fireEvent.click(screen.getByText(`${P}button`))
    fireEvent.click(screen.getByText(`${P}cancel`))
    expect(screen.getByText(`${P}button`)).toBeTruthy()
    expect(screen.queryByText(`${P}ask`)).toBeNull()
  })

  it('a reason tap sends at once with no note', async () => {
    const onDone = jest.fn()
    render(<Host onDone={onDone} />)
    fireEvent.click(screen.getByText(`${P}button`))
    fireEvent.click(screen.getByText(`${R}reasons.water_bill.landlord_pays`))
    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(mockApi.declineResolutionItem).toHaveBeenCalledWith(7, 'landlord_pays', '', { token: 'tkn' })
  })

  it('Other opens a text box and Send stays off until there are words', async () => {
    const onDone = jest.fn()
    render(<Host onDone={onDone} />)
    fireEvent.click(screen.getByText(`${P}button`))
    fireEvent.click(screen.getByText(`${R}reasons.water_bill.other`))
    expect(mockApi.declineResolutionItem).not.toHaveBeenCalled()
    const send = screen.getByText(`${P}send`) as HTMLButtonElement
    expect(send.disabled).toBe(true)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } })
    expect(send.disabled).toBe(true)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'We rent a room.' } })
    expect(send.disabled).toBe(false)
    fireEvent.click(send)
    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(mockApi.declineResolutionItem).toHaveBeenCalledWith(7, 'other', 'We rent a room.', { token: 'tkn' })
  })

  it('a failed send shows a plain error and does not close', async () => {
    mockApi.declineResolutionItem.mockRejectedValue(new Error('x'))
    const onDone = jest.fn()
    render(<Host onDone={onDone} />)
    fireEvent.click(screen.getByText(`${P}button`))
    fireEvent.click(screen.getByText(`${R}reasons.water_bill.landlord_pays`))
    expect(await screen.findByText(`${P}error`)).toBeTruthy()
    expect(onDone).not.toHaveBeenCalled()
  })

  it('a required ask (no reasons served) draws nothing', () => {
    const { container } = render(<Host item={{ ...ITEM, decline_reasons: [] }} />)
    expect(container.innerHTML).toBe('')
  })
})
