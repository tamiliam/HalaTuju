/**
 * @jest-environment jsdom
 *
 * Audit sprint A2.8a (TD-400): when the parent's IC was only half read during our outage, the consent
 * refusal says "try later" (the existing blocker words), never the generic "something went wrong".
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import ScholarshipConsent from './ScholarshipConsent'
import * as api from '@/lib/api'

// Resolve real en copy (with {placeholders}); a missing key comes back as the key, like the real hook.
jest.mock('@/lib/i18n', () => {
  const en = require('@/messages/en.json')
  const look = (k: string): string | undefined =>
    k.split('.').reduce((o: any, p: string) => (o == null ? o : o[p]), en)
  const t = (k: string, p?: Record<string, string>) => {
    const v = look(k)
    return typeof v !== 'string' ? k : v.replace(/\{(\w+)\}/g, (_m, n) => p?.[n] ?? '')
  }
  return { useT: () => ({ t, locale: 'en' }) }
})
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const STATUS = {
  is_minor: true, consent_version: 'v', consents: [], student_name: 'PELAJAR CONTOH',
  student_nric: '110101-14-5678', student_gender: '', parent_ic_vision_nric: '', parent_ic_vision_name: '',
  blockers: [],
} as unknown as api.ConsentStatus

async function fillAndSubmit(code: string) {
  mockApi.getConsentStatus.mockResolvedValue(STATUS)
  mockApi.listDocuments.mockResolvedValue({ documents: [{ doc_type: 'parent_ic' }] } as never)
  mockApi.recordConsent.mockRejectedValueOnce(Object.assign(new Error('400'), { code }))
  render(<ScholarshipConsent token="tok" locale="en" />)
  // The switch renders before the status loads; wait for the minor-only textboxes (slow under load).
  const [name, nric] = await screen.findAllByRole('textbox')
  fireEvent.change(name, { target: { value: 'IBU CONTOH' } })
  fireEvent.change(nric, { target: { value: '750101145678' } })
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'mother' } })
  fireEvent.click(screen.getByRole('switch'))
  await act(async () => { fireEvent.submit(screen.getByRole('switch').closest('form') as HTMLFormElement) })
}

beforeEach(() => jest.clearAllMocks())

it('TD-400: a half-read parent IC refusal says try later', async () => {
  await fillAndSubmit('parent_ic_service_down')
  expect(await screen.findByText(/temporarily unavailable/)).toBeTruthy()
  expect(mockApi.recordConsent).toHaveBeenCalledTimes(1)
})

it('any other refusal keeps the generic line', async () => {
  await fillAndSubmit('parent_ic_nric_mismatch')
  expect(await screen.findByText(/Could not record your consent/)).toBeTruthy()
})

async function renderWith(blockers: string[]) {
  mockApi.getConsentStatus.mockResolvedValue({ ...STATUS, is_minor: false, blockers } as never)
  mockApi.listDocuments.mockResolvedValue({ documents: [] } as never)
  render(<ScholarshipConsent token="tok" locale="en" />)
  await screen.findByRole('switch')
  // The switch renders before the status loads: wait for the list itself, or the first case
  // can read the page before its blockers arrive.
  if (blockers.length) await screen.findByText(/Before you can give consent/)
  else await act(async () => { await Promise.resolve() })
}

describe('Fix 4a: each blocker names the document, the person and the action', () => {
  it.each([
    ['parent_ic_missing:father', /clear photo of the front of Father's IC/],
    ['salary_slip_missing:mother', /Mother's latest salary slip/],
    ['str_needs_recipient_ic:guardian', /Legal guardian's STR page that shows their IC number/],
    ['income_evidence_missing:brother', /Elder brother's income/],
    ['income_doc_unapproved:sister', /Elder sister's income document signed and stamped/],
    ['ic_missing', /clear photo of the front of your own IC/],
    ['str_stale:2025', /Your STR is from 2025/],
  ])('%s', async (code, text) => {
    await renderWith([code])
    expect(screen.getByText(text)).toBeTruthy()
  })

  it('an unknown code shows the safe generic line, never a raw key', async () => {
    await renderWith(['brand_new_code:father'])
    expect(screen.getByText(/One item in the Documents step still needs your attention/)).toBeTruthy()
    expect(screen.queryByText(/scholarship\.consent/)).toBeNull()
  })

  it('shows the Partial match note under the list', async () => {
    await renderWith(['ic_missing'])
    expect(screen.getByText(/"Partial match" mark on your own IC does not stop you giving consent/)).toBeTruthy()
  })

  it('shows the Partial match note for a parent IC item too', async () => {
    await renderWith(['parent_ic_missing:father'])
    expect(screen.getByText(/Partial match/)).toBeTruthy()
  })

  it('no IC item listed: no Partial match note', async () => {
    await renderWith(['results_slip_missing', 'str_needs_recipient_ic'])
    expect(screen.getByText(/Before you can give consent/)).toBeTruthy()
    expect(screen.queryByText(/Partial match/)).toBeNull()
  })

  it('no blockers: no list and no note', async () => {
    await renderWith([])
    expect(screen.queryByText(/Before you can give consent/)).toBeNull()
    expect(screen.queryByText(/Partial match/)).toBeNull()
  })
})
