/**
 * @jest-environment jsdom
 *
 * Request #70 — SAY EXACTLY WHAT IS MISSING before Recommend or Decline. The list under the buttons names each
 * missing item and takes the reviewer to it; a press on a greyed button shows the same list as a focused alert and
 * never acts; the phone bar follows the same rule. (The pure rule is `decisionMissing`, tested in officerCockpit.)
 */
import { act, fireEvent, screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildInterviewSession } from '@/test/adminApplicationDetail'
import { joinFacts } from './view/DecisionMissing'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

installCockpitConsoleGuard()
beforeAll(() => { Element.prototype.scrollIntoView = jest.fn() })   // jsdom has none

const loaded = () => screen.findByText('Test Student 07')
const K = 'admin.scholarship.recordVerdict.'
const btn = (key: string) => screen.getByRole('button', { name: `admin.scholarship.${key}` }) as HTMLButtonElement
const outcome = () => (document.querySelector('[data-bar-outcome]') as HTMLElement).textContent

const nothingDone = () => ({
  officer_verdict: { identity: 'pass', academic: '', income: '', pathway: 'pass', overall: '' },
  verdict_reason: '',
  interview_session: buildInterviewSession({ status: 'draft' }),
})
const readyCase = () => ({
  officer_verdict: { identity: 'pass', academic: 'pass', income: 'pass', pathway: 'pass', overall: '' },
  verdict_reason: 'The evidence supports it.',
  interview_session: buildInterviewSession({ status: 'submitted', findings: {} }),
  interview_agenda: [],
})

describe('the "Still to do" list', () => {
  it('names each missing item, in the page order, and each takes you to its place', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: nothingDone() })
    await loaded()
    const list = document.getElementById('decision-missing') as HTMLElement
    expect(list.getAttribute('role')).toBeNull()   // plain until a press
    const items = Array.from(list.querySelectorAll('li button')) as HTMLButtonElement[]
    expect(items.map((b) => b.textContent)).toEqual([
      K + 'missing.submit', K + 'missing.rate', K + 'missing.conclusion'])
    const targets = ['interview-section', 'rate-fact-academic-pass', 'verdict-reason']
    items.forEach((b, i) => {
      const el = document.getElementById(targets[i]) as HTMLElement
      expect(el).not.toBeNull()
      fireEvent.click(b)
      expect(document.activeElement).toBe(el)
    })
  })

  it('is gone once everything is done', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: readyCase() })
    await loaded()
    expect(document.getElementById('decision-missing')).toBeNull()
  })

  it('is not drawn for a viewer with no write right (nor are the buttons or the phone bar)', async () => {
    renderCockpit({ role: 'reviewer', stage: 'interviewing', build: nothingDone() })
    await loaded()
    expect(document.getElementById('decision-missing')).toBeNull()
    expect(screen.queryByRole('button', { name: `admin.scholarship.recordVerdict.approve` })).toBeNull()
    expect(screen.queryByRole('button', { name: /admin\.scholarship\.decisionBar\.go/ })).toBeNull()
  })
})

describe('a press on a greyed Recommend or Decline', () => {
  it.each(['recordVerdict.approve', 'recordVerdict.decline'])('%s: shows the list as a focused alert and does not act', async (key) => {
    const { api } = renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: nothingDone() })
    await loaded()
    const b = btn(key)
    expect(b.disabled).toBe(false)                          // focusable and clickable
    expect(b.getAttribute('aria-disabled')).toBe('true')
    fireEvent.click(b)
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toContain(K + 'missing.conclusion')
    expect(document.activeElement).toBe(alert)
    expect(outcome()).toBe('—')                             // nothing was chosen
    expect(api.recordVerdict).not.toHaveBeenCalled()
  })

  it('a second press focuses the alert again', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: nothingDone() })
    await loaded()
    fireEvent.click(btn('recordVerdict.approve'))
    const first = screen.getByRole('alert')
    expect(document.activeElement).toBe(first)
    ;(document.getElementById('verdict-reason') as HTMLElement).focus()
    expect(document.activeElement).not.toBe(first)
    fireEvent.click(btn('recordVerdict.decline'))
    expect(document.activeElement).toBe(screen.getByRole('alert'))
  })

  it('goes back to a plain list once an item is fixed, so it is not announced again on every fix', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: nothingDone() })
    await loaded()
    fireEvent.click(btn('recordVerdict.approve'))
    expect(screen.getByRole('alert')).toBeTruthy()
    fireEvent.change(document.getElementById('verdict-reason') as HTMLTextAreaElement,
      { target: { value: 'The evidence supports it.' } })
    expect(screen.queryByRole('alert')).toBeNull()
    const list = document.getElementById('decision-missing') as HTMLElement
    expect(list).not.toBeNull()
    expect(list.textContent).not.toContain(K + 'missing.conclusion')
  })

  it('a ready decision with no bursary amount: Recommend shows the reason as a focused alert and does not act', async () => {
    const { api } = renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing',
      build: { ...readyCase(), award_amount: null, proposed_award_amount: null } })
    await loaded()
    expect(btn('recordVerdict.approve').getAttribute('aria-disabled')).toBe('true')
    expect(screen.queryByRole('alert')).toBeNull()
    fireEvent.click(btn('recordVerdict.approve'))
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toBe(K + 'approveNeedsAmount')
    expect(document.activeElement).toBe(alert)
    expect(outcome()).toBe('—')
    expect(api.recordVerdict).not.toHaveBeenCalled()
    // Decline needs no amount and still works.
    fireEvent.click(btn('recordVerdict.decline'))
    expect(outcome()).toBe('admin.scholarship.recordVerdict.decline')
  })

  it('a ready case still chooses the outcome on a press', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: readyCase() })
    await loaded()
    expect(btn('recordVerdict.approve').getAttribute('aria-disabled')).toBeNull()
    fireEvent.click(btn('recordVerdict.decline'))
    expect(outcome()).toBe('admin.scholarship.recordVerdict.decline')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('the phone decision bar', () => {
  it('a press while something is missing shows the same list as an alert', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: nothingDone() })
    await loaded()
    expect(screen.queryByRole('alert')).toBeNull()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /admin\.scholarship\.decisionBar\.go/ }))
    })
    expect(screen.getByRole('alert').textContent).toContain(K + 'missing.submit')
  })

  it('a press when ready only jumps', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing', build: readyCase() })
    await loaded()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /admin\.scholarship\.decisionBar\.go/ }))
    })
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('the fact list reads as the language does, with the real messages', () => {
  const cat = { en, ms, ta } as Record<string, any>
  const real = (loc: string) => (key: string, params: Record<string, string> = {}) => {
    const v = key.split('.').reduce((o, k) => o?.[k], cat[loc]) as string
    return Object.entries(params).reduce((acc, [k, x]) => acc.replace(`{${k}}`, x), v)
  }
  it.each([
    ['en', 'Check Academic and Income'],
    ['ms', 'Semak fakta: Akademik dan Pendapatan'],
    ['ta', 'உண்மைகளைச் சரிபாருங்கள்: கல்வி மற்றும் வருமானம்'],
  ])('%s', (loc, expected) => {
    const t = real(loc)
    const facts = joinFacts(['academic', 'income'].map((f) => t(`admin.scholarship.verdict.fact.${f}`)), loc)
    expect(t(K + 'missing.rate', { facts })).toBe(expected)
  })
})
