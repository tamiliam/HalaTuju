/**
 * Guardrail: the suite-wide limits in `jest.setup.ts` are actually in force.
 *
 * They exist because the deploy gate runs this suite on a small, busy worker, where Testing
 * Library's default one-second async limit turned two healthy rendered tests red (code health H4).
 * If `setupFilesAfterEnv` is ever dropped from jest.config.js, nothing fails on a fast dev box —
 * the flake simply comes back in the gate, weeks later, and blocks a deploy. This test fails
 * at once instead.
 */
import { getConfig } from '@testing-library/dom'

describe('jest.setup.ts is wired in', () => {
  it('raises the async helper limit well above the one-second default', () => {
    expect(getConfig().asyncUtilTimeout).toBeGreaterThanOrEqual(10_000)
  })
})
