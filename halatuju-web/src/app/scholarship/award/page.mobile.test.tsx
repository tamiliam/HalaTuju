/**
 * @jest-environment jsdom
 *
 * Mobile M4 — the award page on a phone, and the two owner rulings it carries:
 *   * a reload SKIPS what the server already holds as done (the quiz on this template, a parent PIN
 *     still inside its window) — read from `bursary_preview`, never remembered by the browser;
 *   * the agreement opens in a reader sheet, its server HTML byte-for-byte unchanged behind a phone
 *     stylesheet; and Decline asks in a sheet (it used the browser's own confirm).
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarshipAwardPage from './page'
import * as api from '@/lib/api'
import { PHONE_CONTRACT_CSS, phoneContractHtml } from '@/components/scholarship/AwardContract'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({ status: 'authenticated', token: 'tok' }) }))
const mockPush = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush, replace: jest.fn() }) }))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/components/AwardComprehensionQuiz', () => ({
  __esModule: true, default: () => <div data-testid="quiz-step" />,
}))
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const OFFER = { amount: '3000', accept_deadline: null } as unknown as api.StudentAward
const SERVER_HTML = '<html><head><meta charset="utf-8"/></head><body style="font-size: 11px;">'
  + '<h1 style="font-size:18px">Agreement</h1><p>1.1 The Bursary is RM 3,000.00.</p></body></html>'
const preview = (extra: object = {}) => ({
  award_amount: '3000', payment_schedule: 'RM 250 a month', institution_name: 'UM', course_name: 'CS',
  progress_standard: '', foundation_signatory_name: 'S', foundation_signatory_title: 'T',
  rendered_html: SERVER_HTML, ...extra,
})
const serve = (body: object) => mockApi.getStudentAward.mockResolvedValue({
  offer: OFFER, finalising: false, is_minor: false, acceptance_enabled: true, ...body,
} as unknown as Awaited<ReturnType<typeof api.getStudentAward>>)

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.respondToAward.mockResolvedValue({} as never)
})

describe('a reload skips what the server holds as done (owner ruling)', () => {
  it('quiz not passed on this template → the quiz step', async () => {
    serve({ bursary_preview: preview({ comprehension_passed: false }) })
    render(<ScholarshipAwardPage />)
    expect(await screen.findByTestId('quiz-step')).toBeTruthy()
  })

  it('quiz passed → straight to Read & sign', async () => {
    serve({ bursary_preview: preview({ comprehension_passed: true }) })
    render(<ScholarshipAwardPage />)
    expect(await screen.findByText('scholarship.award.bursary.student.title')).toBeTruthy()
    expect(screen.queryByTestId('quiz-step')).toBeNull()
  })

  it('a parent PIN still valid → shown as verified, no second SMS offered', async () => {
    serve({ bursary_preview: preview({ comprehension_passed: true, guarantor_phone_verified: true }) })
    render(<ScholarshipAwardPage />)
    expect(await screen.findByText('scholarship.award.bursary.guarantor.pin.verified')).toBeTruthy()
    expect(screen.queryByText('scholarship.award.bursary.guarantor.pin.send')).toBeNull()
  })

  it('an expired or absent PIN check → the Send PIN step, as before', async () => {
    serve({ bursary_preview: preview({ comprehension_passed: true, guarantor_phone_verified: false }) })
    render(<ScholarshipAwardPage />)
    expect(await screen.findByText('scholarship.award.bursary.guarantor.pin.send')).toBeTruthy()
  })

  it('an older API without the fields → nothing is skipped', async () => {
    serve({ bursary_preview: preview() })
    render(<ScholarshipAwardPage />)
    expect(await screen.findByTestId('quiz-step')).toBeTruthy()
  })
})

describe('the agreement on a phone', () => {
  it('the stylesheet goes IN FRONT of the server HTML, which follows byte for byte', () => {
    const out = phoneContractHtml(SERVER_HTML)
    expect(out.startsWith(PHONE_CONTRACT_CSS)).toBe(true)
    expect(out.slice(PHONE_CONTRACT_CSS.length)).toBe(SERVER_HTML)
    expect(PHONE_CONTRACT_CSS).not.toMatch(/<script|content:|::before|::after|display:\s*none|visibility/i)
  })

  it('"Read the full agreement" opens a sandboxed reader with that document', async () => {
    serve({ bursary_preview: preview({ comprehension_passed: true }) })
    render(<ScholarshipAwardPage />)
    fireEvent.click(await screen.findByTestId('award-read-agreement'))
    const reader = await screen.findByTestId('award-reader')
    const frame = reader.querySelector('iframe') as HTMLIFrameElement
    expect(frame.getAttribute('sandbox')).toBe('')
    expect(frame.getAttribute('srcdoc')).toBe(PHONE_CONTRACT_CSS + SERVER_HTML)
    fireEvent.click(screen.getByRole('button', { name: 'scholarship.actionCentre.done' }))
    await waitFor(() => expect(screen.queryByTestId('award-reader')).toBeNull())
  })
})

describe('Decline asks in a sheet', () => {
  const confirmSpy = () => jest.spyOn(window, 'confirm')

  it('signing page: Decline opens the sheet; Cancel sends nothing; Decline there sends one decline', async () => {
    const ask = confirmSpy()
    serve({ bursary_preview: preview({ comprehension_passed: true }) })
    render(<ScholarshipAwardPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'scholarship.award.confirmed.decline' }))
    const sheet = await screen.findByTestId('award-decline')
    expect(mockApi.respondToAward).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'scholarship.award.guardian.cancel' }))
    await waitFor(() => expect(screen.queryByTestId('award-decline')).toBeNull())
    expect(mockApi.respondToAward).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'scholarship.award.confirmed.decline' }))
    await screen.findByTestId('award-decline')
    const go = Array.from(screen.getByTestId('award-decline').querySelectorAll('button'))
      .find((b) => b.textContent === 'scholarship.award.confirmed.decline') as HTMLButtonElement
    await act(async () => { fireEvent.click(go); fireEvent.click(go) })
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/scholarship/application'))
    expect(mockApi.respondToAward).toHaveBeenCalledTimes(1)
    expect(mockApi.respondToAward.mock.calls[0][0]).toEqual({ action: 'decline', locale: 'en' })
    expect(ask).not.toHaveBeenCalled()
    expect(sheet).toBeTruthy()
    ask.mockRestore()
  })

  it('plain offer: the same sheet, never the browser confirm', async () => {
    const ask = confirmSpy()
    serve({})
    render(<ScholarshipAwardPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'scholarship.award.confirmed.decline' }))
    expect(await screen.findByTestId('award-decline')).toBeTruthy()
    expect(ask).not.toHaveBeenCalled()
    expect(mockApi.respondToAward).not.toHaveBeenCalled()
    ask.mockRestore()
  })

  it('Decline and Resend are 44 px targets; the agree rows are 44 px tall', async () => {
    serve({ bursary_preview: preview({ comprehension_passed: true }) })
    render(<ScholarshipAwardPage />)
    const decline = await screen.findByRole('button', { name: 'scholarship.award.confirmed.decline' })
    expect(decline.className).toMatch(/\bmin-h-11\b/)
    const agree = screen.getByText('scholarship.award.bursary.student.agree').closest('label') as HTMLLabelElement
    expect(agree.className).toMatch(/\bmin-h-11\b/)
  })
})

describe('one answer to the award, however many taps (Mobile M4 latch)', () => {
  it('Sign and accept pressed twice in the same frame: ONE accept is sent', async () => {
    let finish: () => void = () => {}
    mockApi.respondToAward.mockImplementation(() => new Promise((r) => { finish = () => r({} as never) }))
    serve({ bursary_preview: preview({ comprehension_passed: true, guarantor_phone_verified: true }) })
    render(<ScholarshipAwardPage />)
    await screen.findByText('scholarship.award.bursary.student.title')
    fireEvent.click(screen.getByTestId('award-read-agreement'))        // review M1: shown before agreeing
    fireEvent.change(screen.getByPlaceholderText('scholarship.award.bursary.student.signPlaceholder'), { target: { value: 'Zxq Student' } })
    fireEvent.change(screen.getByPlaceholderText('scholarship.award.bursary.guarantor.namePlaceholder'), { target: { value: 'Rahmah' } })
    fireEvent.change(screen.getByDisplayValue('scholarship.award.guardian.relationshipPlaceholder'), { target: { value: 'mother' } })
    const nrics = screen.getAllByPlaceholderText('XXXXXX-XX-XXXX')
    fireEvent.change(nrics[nrics.length - 1], { target: { value: '700101105555' } })
    for (const box of screen.getAllByRole('checkbox')) fireEvent.click(box)
    const form = screen.getByRole('button', { name: 'scholarship.award.bursary.signSubmit' }).closest('form') as HTMLFormElement
    await act(async () => { fireEvent.submit(form); fireEvent.submit(form) })
    await act(async () => { finish() })
    expect(mockApi.respondToAward).toHaveBeenCalledTimes(1)
    expect(mockApi.respondToAward.mock.calls[0][0]).toMatchObject({ action: 'accept', guarantor_name: 'Rahmah' })
  })
})

/** Fill the signing form completely (PIN already valid from the server). */
async function fillSigning() {
  await screen.findByText('scholarship.award.bursary.student.title')
  fireEvent.change(screen.getByPlaceholderText('scholarship.award.bursary.student.signPlaceholder'), { target: { value: 'Zxq Student' } })
  fireEvent.change(screen.getByPlaceholderText('scholarship.award.bursary.guarantor.namePlaceholder'), { target: { value: 'Rahmah' } })
  fireEvent.change(screen.getByDisplayValue('scholarship.award.guardian.relationshipPlaceholder'), { target: { value: 'mother' } })
  const nrics = screen.getAllByPlaceholderText('XXXXXX-XX-XXXX')
  fireEvent.change(nrics[nrics.length - 1], { target: { value: '700101105555' } })
}
const signButton = () => screen.getByRole('button', { name: 'scholarship.award.bursary.signSubmit' }) as HTMLButtonElement

describe('review M1 — she can agree only to an agreement that was put in front of her', () => {
  it('phone: the agree ticks and Sign stay off until "Read the full agreement" is opened', async () => {
    serve({ bursary_preview: preview({ comprehension_passed: true, guarantor_phone_verified: true }) })
    render(<ScholarshipAwardPage />)
    await fillSigning()
    const boxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
    expect(boxes.every((b) => b.disabled)).toBe(true)
    for (const b of boxes) fireEvent.click(b)
    expect(boxes.some((b) => b.checked)).toBe(false)
    expect(signButton().disabled).toBe(true)
    fireEvent.click(screen.getByTestId('award-read-agreement'))
    fireEvent.click(screen.getByRole('button', { name: 'scholarship.actionCentre.done' }))
    for (const b of screen.getAllByRole('checkbox')) fireEvent.click(b)
    expect(signButton().disabled).toBe(false)
  })

  it('a wider screen shows the agreement inline — that counts as shown', async () => {
    const mm = window.matchMedia
    window.matchMedia = ((q: string) => ({ matches: q.includes('768'), media: q, addEventListener() {}, removeEventListener() {} })) as never
    try {
      serve({ bursary_preview: preview({ comprehension_passed: true, guarantor_phone_verified: true }) })
      render(<ScholarshipAwardPage />)
      await fillSigning()
      await waitFor(() => expect((screen.getAllByRole('checkbox') as HTMLInputElement[]).every((b) => !b.disabled)).toBe(true))
    } finally {
      window.matchMedia = mm
    }
  })
})

describe('review M2 / M3 — after an answer, and after a refusal', () => {
  it('M2: a tap during the navigation that follows a successful accept sends nothing', async () => {
    serve({})
    render(<ScholarshipAwardPage />)
    const accept = await screen.findByRole('button', { name: 'scholarship.award.confirmed.accept' })
    await act(async () => { fireEvent.click(accept) })
    await waitFor(() => expect(mockApi.respondToAward).toHaveBeenCalledTimes(1))
    await act(async () => { fireEvent.click(accept) })                   // the page has not gone yet
    expect(mockApi.respondToAward).toHaveBeenCalledTimes(1)
  })

  it('M3: a refused signature brings the reason into view (it sits up the page, the button at the bottom)', async () => {
    const scroll = jest.fn()
    const orig = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scroll
    const raf = jest.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => { cb(0); return 0 })
    try {
      mockApi.respondToAward.mockRejectedValueOnce(Object.assign(new Error('400'), { code: 'parent_ic_name_mismatch' }))
      serve({ bursary_preview: preview({ comprehension_passed: true, guarantor_phone_verified: true }) })
      render(<ScholarshipAwardPage />)
      await fillSigning()
      fireEvent.click(screen.getByTestId('award-read-agreement'))
      for (const b of screen.getAllByRole('checkbox')) fireEvent.click(b)
      await act(async () => { fireEvent.submit(signButton().closest('form') as HTMLFormElement) })
      expect(await screen.findByText('scholarship.award.error.parent_ic_name_mismatch')).toBeTruthy()
      expect(scroll).toHaveBeenCalled()
      // ...and the lock is released: she can correct and sign again.
      expect(signButton().disabled).toBe(false)
    } finally {
      Element.prototype.scrollIntoView = orig
      raf.mockRestore()
    }
  })
})

