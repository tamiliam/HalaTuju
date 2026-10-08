/**
 * @jest-environment jsdom
 *
 * Request #31 (BrightPath, 2026-10-08) — the reviewer sees where the IC says the student was born.
 *
 * ⚠ THE LINE IS THE SERVER'S. `birth_state.label` is read from the IC's place-of-birth code and
 * worded on the server (English, to keep `en.json` flat — TD-360; served on the ADMIN payload
 * only); the cockpit prints it beside the NRIC and never re-reads the number itself.
 *
 * ⚠ `meets_rule` IS RE-READ ON EVERY LOAD (request #31 review). The gate ran at submit, and an
 * unverified NRIC can be changed afterwards; when the CURRENT IC fails the intake's CURRENT rule
 * the line becomes the served warning, and the QC panel shows the same fact on its accept floor —
 * so the override box appears on screen instead of the server's 400 arriving unexplained.
 */
import { fireEvent, screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

describe('the place of birth beside the NRIC', () => {
  it('prints the served line in the case header', async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted' })
    await loaded()
    expect(screen.getByTestId('birth-state').textContent)
      .toBe('Born in: W.P. Kuala Lumpur (IC code 14)')
  })

  it('prints a fail-closed reading just as plainly', async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted', build: {
      birth_state: { kind: 'abroad', state: null, code: '71',
                     label: 'Born outside Malaysia (IC code 71)', meets_rule: null, warning: '' },
    } })
    await loaded()
    expect(screen.getByTestId('birth-state').textContent).toBe('Born outside Malaysia (IC code 71)')
  })

  it("turns into the served WARNING when the current IC fails the intake's rule", async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted', build: { birth_state: FAILS } })
    await loaded()
    expect(screen.getByTestId('birth-state').textContent).toBe(FAILS.warning)
  })
})

/** A student whose IC was changed after the gate (the review's finding 1). */
const FAILS = {
  kind: 'state' as const, state: 'selangor', code: '10', label: 'Born in: Selangor (IC code 10)',
  meets_rule: false,
  warning: "Born in: Selangor (IC code 10) — does not meet this intake's rule (Sabah)",
}

describe('the QC accept floor', () => {
  const FLOOR = 'admin.scholarship.qcDecision.gapFloor'
  const accept = () => screen.getByRole('button', { name: 'admin.scholarship.qcDecision.accept' })

  it('shows the floor and asks for a reason instead of sending the accept', async () => {
    const { api } = renderCockpit({ role: 'qc', stage: 'awaiting_qc', build: {
      outcome: 'recommend', birth_state: FAILS } })
    await loaded()
    expect(screen.getByText(FLOOR, { exact: false })).toBeTruthy()
    fireEvent.click(accept())
    expect(screen.getByText('admin.scholarship.qcDecision.overrideTitle')).toBeTruthy()
    expect(api.recordQcDecision).not.toHaveBeenCalled()
  })

  it('stays out of the way when the intake has no rule', async () => {
    renderCockpit({ role: 'qc', stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(screen.queryByText(FLOOR, { exact: false })).toBeNull()
  })
})
