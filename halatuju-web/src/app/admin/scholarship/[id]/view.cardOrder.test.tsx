/**
 * @jest-environment jsdom
 *
 * Owner 2026-11-24 (TD-720): Estimated need sits ABOVE Reviewer Assessment at every stage, so the
 * assessment box sits next to the Recommendation box below it.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const ESTIMATE = 'admin.scholarship.estimate.title'
const RATE = 'admin.scholarship.recordVerdict.rateTitle'
const follows = (a: Node, b: Node) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0

describe.each(['assigned', 'interviewing', 'recommended'] as const)('at %s', (stage) => {
  it('Estimated need comes first, then Reviewer Assessment, then the Recommendation', async () => {
    renderCockpit({ role: 'org_admin', writes: true, stage })
    await screen.findByText('Test Student 07')
    const estimate = screen.getByText(ESTIMATE)
    const rate = screen.getByText(RATE)
    expect(follows(estimate, rate)).toBe(true)
    const decision = document.getElementById('decision-section')
    expect(decision).toBeTruthy()
    expect(follows(rate, decision as Node)).toBe(true)
  })
})
