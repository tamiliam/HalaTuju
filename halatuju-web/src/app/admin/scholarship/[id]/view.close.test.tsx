/**
 * @jest-environment jsdom
 *
 * TD-352 — AN OFFICER CLOSES A STALLED APPLICATION (owner ruling, option A, 2026-10-06).
 *
 * An application in play stops the student starting another. A case that stopped moving would
 * hold her place for ever, so the Close card now shows at EVERY in-play status, with the reasons
 * the api accepts at that stage (`lib/closeOffer`, drift-tested against `closure.py`): before an
 * award only "No movement" and "Withdrawn"; at active / maintenance, the funded list plus "No
 * movement"; at awarded, none (the offer is always out — TD-366).
 * A finished case shows no card. The api's `sponsorship_open` refusal (a live offer or paid money)
 * is answered by the server and shown in the card.
 */
import { act, fireEvent, screen, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const TITLE = 'admin.closure.title'

/** The Close card — the element holding its heading. */
const card = () => screen.getByText(TITLE).parentElement as HTMLElement
/** The reason codes the dropdown offers, in order (the first option is the "choose" prompt). */
const reasons = () => within(card()).getAllByRole('option').slice(1)
  .map((o) => (o as HTMLOptionElement).value)

describe('before an award — stalled and withdrawn only', () => {
  it.each([
    ['submitted', {}],
    ['recommended', {}],
  ] as const)('a %s case shows the Close card with No movement and Withdrawn', async (stage, build) => {
    renderCockpit({ role: 'super', stage, build })
    await loaded()
    expect(reasons()).toEqual(['stalled', 'withdrawn'])
    expect(within(card()).getByText('admin.closure.notePreAward')).toBeTruthy()
    // The funded offboarding checklist is not a pre-award question.
    expect(within(card()).queryByText('admin.closure.checklist.finalDisbursement')).toBeNull()
  })

  it('closes with the chosen reason', async () => {
    const { api, app } = renderCockpit({ role: 'super', stage: 'recommended' })
    await loaded()
    api.closeApplication.mockResolvedValue({ ...app, status: 'closed', closure_reason: 'stalled' })
    fireEvent.change(within(card()).getByRole('combobox'), { target: { value: 'stalled' } })
    await act(async () => {
      fireEvent.click(within(card()).getByRole('button', { name: 'admin.closure.close' }))
    })
    expect(api.closeApplication).toHaveBeenCalledWith(app.id, 'stalled', { token: 'test-token' })
    expect(await screen.findByText('admin.closure.reason.stalled')).toBeTruthy()
  })

  it('shows the sponsorship refusal in the card (e.g. money paid at recommended)', async () => {
    const { api } = renderCockpit({ role: 'super', stage: 'recommended' })
    await loaded()
    api.closeApplication.mockRejectedValue(new Error('sponsorship_open'))
    fireEvent.change(within(card()).getByRole('combobox'), { target: { value: 'stalled' } })
    await act(async () => {
      fireEvent.click(within(card()).getByRole('button', { name: 'admin.closure.close' }))
    })
    expect(within(card()).getByText('admin.closure.error.sponsorship_open')).toBeTruthy()
  })
})

describe('who — a pre-award close is super / org_admin only (the api answers 403 to anyone else)', () => {
  it('an org_admin sees the pre-award Close card', async () => {
    renderCockpit({ role: 'org_admin', stage: 'recommended' })
    await loaded()
    expect(reasons()).toEqual(['stalled', 'withdrawn'])
  })

  it('a qc (who may write) sees no Close card before an award', async () => {
    renderCockpit({ role: 'qc', stage: 'recommended' })
    await loaded()
    expect(screen.queryByText(TITLE)).toBeNull()
  })

  it('a qc still sees the funded Close card', async () => {
    renderCockpit({ role: 'qc', stage: 'active' })
    await loaded()
    expect(reasons()).toContain('graduated')
  })
})

describe('an awarded case — no Close card (TD-366: no door releases it; the api always refuses)', () => {
  it('shows none, even to a super', async () => {
    renderCockpit({ role: 'super', stage: 'awarded' })
    await loaded()
    expect(screen.queryByText(TITLE)).toBeNull()
  })
})

describe('a funded case — the existing list plus No movement', () => {
  it('an active case keeps the old reasons and the checklist', async () => {
    renderCockpit({ role: 'super', stage: 'active' })
    await loaded()
    expect(reasons()).toEqual(['graduated', 'completed', 'withdrawn', 'lapsed', 'terminated', 'stalled'])
    expect(within(card()).getByText('admin.closure.note')).toBeTruthy()
    expect(within(card()).getByText('admin.closure.checklist.finalDisbursement')).toBeTruthy()
  })
})

describe('a finished case — no Close card', () => {
  it.each(['rejected', 'expired'] as const)('a %s case shows none', async (stage) => {
    renderCockpit({ role: 'super', stage })
    await loaded()
    expect(screen.queryByText(TITLE)).toBeNull()
  })

  it('a closed case shows the closed summary, not a control', async () => {
    renderCockpit({ role: 'super', stage: 'closed' })
    await loaded()
    expect(screen.getByText(TITLE)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'admin.closure.close' })).toBeNull()
  })
})
