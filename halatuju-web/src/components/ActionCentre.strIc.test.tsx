/**
 * @jest-environment jsdom
 *
 * TD-285 (owner's F1 ruling, 2026-09-29) — THE "WHOSE STR IS IT?" IC ASK, RENDERED.
 *
 * When the STR names nobody whose IC is on file and a household member has none, the STR still
 * counts, and after submission Check 2 asks for THAT member's IC: `<member>_ic_for_str_missing`
 * (or `_unreadable` when the IC is on file but the field needed did not read). Review finding F-F:
 * no test rendered any of the new keys, so a copy block could be misnamed and every guard would
 * stay green while the student saw a raw key. This mounts the real Action Centre with the REAL
 * message catalogues — English and Tamil — and asserts what the student reads.
 */
import { render, screen } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'
import { interpolateMessage } from '@/lib/branding'
import en from '@/messages/en.json'
import ta from '@/messages/ta.json'

const CATALOGUES: Record<string, unknown> = { en, ta }
let locale: 'en' | 'ta' = 'en'

/** The real catalogue lookup, as `useT` does it, for whichever locale the test set. */
const lookup = (key: string, params?: Record<string, string>): string => {
  const value = key.split('.').reduce<unknown>(
    (node, part) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[part] : undefined),
    CATALOGUES[locale])
  return typeof value === 'string' ? interpolateMessage(value, params) : key
}

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  resolveResolutionItem: jest.fn(),
  listDocuments: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: lookup, locale }) }))
jest.mock('./DocumentHelpCoach', () => ({
  __esModule: true, default: () => null, CoachCard: () => null,
}))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const ASK = (code: string): ResolutionItem => ({
  id: 31, fact: 'income', code, params: { household_member: 'mother' },
  prompt: '', kind: 'doc', doc_type: 'parent_ic', status: 'open',
  source: 'check2' as ResolutionItem['source'], resolution_text: '',
  created_at: '2026-09-29T09:00:00.000Z', resolved_at: null,
})

const mount = async (code: string, title: string) => {
  mockApi.getResolutionItems.mockResolvedValue({ open: [ASK(code)], resolved: [] })
  mockApi.listDocuments.mockResolvedValue({ documents: [] })
  render(<ActionCentre token="test-token" studentName="Test Student 07" applicationId={7} />)
  return screen.findByText(title)
}

beforeEach(() => { jest.clearAllMocks(); locale = 'en' })

describe('the mother variant, as the student reads it', () => {
  it('English: names HER IC, and says why', async () => {
    expect(await mount('mother_ic_for_str_missing', "Upload your mother's IC")).toBeTruthy()
    expect(screen.getByText(/so we can confirm it is your household's/)).toBeTruthy()
    expect(screen.queryByText(/scholarship\.actionCentre\.item/)).toBeNull()   // no raw key
  })

  it('Tamil: the same ask, in Tamil, naming தாய்', async () => {
    locale = 'ta'
    expect(await mount('mother_ic_for_str_missing',
                       'உங்கள் தாயின் அடையாள அட்டையைப் பதிவேற்றவும்')).toBeTruthy()
    expect(screen.queryByText(/scholarship\.actionCentre\.item/)).toBeNull()
  })

  it('an IC ON FILE that could not be read is asked again, not called missing (review F-C)',
     async () => {
    expect(await mount('mother_ic_for_str_unreadable', "Re-upload your mother's IC")).toBeTruthy()
    expect(screen.queryByText("Upload your mother's IC")).toBeNull()
  })
})
