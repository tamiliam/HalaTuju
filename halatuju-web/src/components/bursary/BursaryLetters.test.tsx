/**
 * @jest-environment jsdom
 *
 * Her Letters tab on My Bursary (student maintenance S6b). Pinned:
 *  * each state in her words; an unread dot until she opens it (which tells the server);
 *  * "I have read this letter" with "It does not mean you agree" beside it; afterwards the date;
 *  * a withdrawn letter says she need do nothing and offers no acknowledgement;
 *  * the PDF language is named on the download.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import BursaryLetters from './BursaryLetters'
import * as api from '@/lib/api/bursaryLetters'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'ta' }),
}))
jest.mock('@/lib/api/bursaryLetters')
const mockApi = api as jest.Mocked<typeof api>
const P = 'bursaryTabs.letters'

const letter = (id: number, over: Partial<api.BursaryLetter> = {}): api.BursaryLetter => ({
  id, kind: 'discipline', language: 'ms', subject: `Letter ${id}`, body: 'Salam Aisyah', issued_at: '2026-10-02T00:00:00Z',
  response_due_on: '2026-10-16', acknowledged_at: null, withdrawn_at: null, read: false, state: 'overdue', has_pdf: true,
  ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getBursaryLetters.mockResolvedValue({ organisation: 'BrightPath Foundation', letters: [
    letter(1),
    letter(2, { kind: 'general', state: 'acknowledged', read: true, acknowledged_at: '2026-09-03T00:00:00Z' }),
    letter(3, { kind: 'suspension', state: 'withdrawn', withdrawn_at: '2026-08-20T00:00:00Z' }),
  ] })
  mockApi.markLetterRead.mockImplementation(async (id: number) => letter(id, { read: true }))
})

it('lists her letters in her words, with an unread dot', async () => {
  render(<BursaryLetters token="tok" onAcknowledged={jest.fn()} />)
  expect((await screen.findByTestId('her-letter-state-1')).textContent).toContain(`${P}.state.overdue`)
  expect(screen.getByTestId('her-letter-state-2').textContent).toContain(`${P}.state.acknowledged`)
  expect(screen.getByTestId('her-letter-state-3').textContent).toContain(`${P}.state.withdrawn`)
  expect(within(screen.getByTestId('her-letter-1')).getByRole('img', { name: `${P}.unread` })).toBeTruthy()
  expect(within(screen.getByTestId('her-letter-2')).queryByRole('img')).toBeNull()
})

it('opening tells the server she read it; acknowledging says it is not agreement', async () => {
  const onAck = jest.fn()
  mockApi.acknowledgeLetter.mockResolvedValue(letter(1, { read: true, state: 'acknowledged', acknowledged_at: '2026-10-31T00:00:00Z' }))
  render(<BursaryLetters token="tok" onAcknowledged={onAck} />)
  fireEvent.click(await screen.findByTestId('her-letter-1'))
  await waitFor(() => expect(mockApi.markLetterRead).toHaveBeenCalledWith(1, { token: 'tok' }))
  const view = screen.getByTestId('her-letter-read')
  expect(within(view).getByText(`${P}.notAgreement|{"organisation":"BrightPath Foundation"}`)).toBeTruthy()
  expect(within(view).getByText(`${P}.download|{"language":"${P}.pdfLang.ms"}`)).toBeTruthy()
  fireEvent.click(within(view).getByText(`${P}.acknowledge`))
  await waitFor(() => expect(mockApi.acknowledgeLetter).toHaveBeenCalledWith(1, { token: 'tok' }))
  expect(await screen.findByTestId('her-letter-acked')).toBeTruthy()
  expect(onAck).toHaveBeenCalled()
  expect(within(screen.getByTestId('her-letter-read')).queryByText(`${P}.acknowledge`)).toBeNull()
})

it('a withdrawn letter asks nothing of her', async () => {
  render(<BursaryLetters token="tok" onAcknowledged={jest.fn()} />)
  fireEvent.click(await screen.findByTestId('her-letter-3'))
  const view = screen.getByTestId('her-letter-read')
  expect(within(view).getByText(`${P}.withdrawnNote`)).toBeTruthy()
  expect(within(view).queryByText(`${P}.acknowledge`)).toBeNull()
})
