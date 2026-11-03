/**
 * @jest-environment jsdom
 *
 * Mobile M6b — THE PHONE'S DECISION BAR (owner, 2026-11-03): it shows the chosen outcome and JUMPS to the decision
 * section; Save stays in the section. Two things are pinned here, from what the page renders:
 *
 *  1. The bar shows EXACTLY when the decision card offers Save — over every stage of the funnel, both outcomes
 *     where they exist, and a writer and a reader. `decisionBarShows` copies the card's own condition; if the two
 *     ever disagree, a phone either loses its way to a live decision or is sent to a card with nothing to press.
 *  2. Its button sends NOTHING: pressing it scrolls to the section and calls no endpoint.
 *
 * (jsdom applies no media query, so the `md:hidden` bar is in the DOM at every width here.)
 */
import { act, fireEvent, screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { STAGES, OUTCOME_STAGES, type Stage } from '@/test/adminApplicationDetail'
import type { AdminRoleName } from '@/lib/navigation'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const saveOffered = () => !!screen.queryByRole('button', { name: 'admin.scholarship.recordVerdict.save' })
  || !!screen.queryByRole('button', { name: 'admin.scholarship.recordVerdict.saveDecline' })
const bar = () => document.querySelector('[data-decision-bar]')

const CASES: Array<{ stage: Stage; role: AdminRoleName; outcome?: 'recommend' | 'decline' }> = []
for (const stage of STAGES) {
  for (const role of ['reviewer', 'org_admin'] as AdminRoleName[]) {
    if (OUTCOME_STAGES.includes(stage)) {
      CASES.push({ stage, role, outcome: 'recommend' }, { stage, role, outcome: 'decline' })
    } else CASES.push({ stage, role })
  }
}

describe('the phone decision bar (Mobile M6b)', () => {
  it.each(CASES)('$stage · $role · $outcome: the bar shows exactly when the card offers Save', async ({ stage, role, outcome }) => {
    renderCockpit({ role, stage, build: outcome ? { outcome } : {} })
    await loaded()
    expect(!!bar()).toBe(saveOffered())
  })

  it('the matrix is not empty on either side (the test would pass on an absent bar otherwise)', async () => {
    renderCockpit({ role: 'reviewer', stage: 'interviewing' })
    await loaded()
    expect(saveOffered()).toBe(true)
    expect(bar()).not.toBeNull()
  })

  it('it carries data-page-bar and is a phone-only, sticky bar', async () => {
    renderCockpit({ role: 'reviewer', stage: 'interviewing' })
    await loaded()
    const b = bar() as HTMLElement
    expect(b.hasAttribute('data-page-bar')).toBe(true)
    expect(b.className.split(' ')).toEqual(expect.arrayContaining(['sticky', 'bottom-0', 'md:hidden']))
  })

  it('its button scrolls to the decision section and calls NO endpoint', async () => {
    const { api } = renderCockpit({ role: 'reviewer', stage: 'interviewing' })
    await loaded()
    const section = document.getElementById('decision-section') as HTMLElement
    expect(section).not.toBeNull()
    const scroll = jest.fn()
    section.scrollIntoView = scroll
    const callsBefore = Object.values(api).reduce((n, f) => n + ((f as jest.Mock).mock?.calls.length ?? 0), 0)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /admin\.scholarship\.decisionBar\.go/ }))
    })
    expect(scroll).toHaveBeenCalledTimes(1)
    const callsAfter = Object.values(api).reduce((n, f) => n + ((f as jest.Mock).mock?.calls.length ?? 0), 0)
    expect(callsAfter).toBe(callsBefore)
  })

  it('it names the outcome the card has chosen, and a dash before any', async () => {
    renderCockpit({ role: 'reviewer', stage: 'interviewing' })
    await loaded()
    const outcome = () => (document.querySelector('[data-bar-outcome]') as HTMLElement).textContent
    expect(outcome()).toBe('—')
    const decline = screen.getByRole('button', { name: 'admin.scholarship.recordVerdict.decline' }) as HTMLButtonElement
    if (!decline.disabled) {
      fireEvent.click(decline)
      expect(outcome()).toBe('admin.scholarship.recordVerdict.decline')
    }
  })
})
