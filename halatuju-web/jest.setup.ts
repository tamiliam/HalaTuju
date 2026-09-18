/**
 * Suite-wide test set-up. Loaded by `setupFilesAfterEnv` in jest.config.js.
 *
 * ⚠ WHY THIS FILE EXISTS (code health H4, 2026-09-19). Since H2 this suite runs inside the Cloud
 * Build deploy gate, on a 2-vCPU worker that is ALSO building the production image. Testing
 * Library's async helpers (`findByText`, `waitFor`) give up after ONE second by default. On a dev
 * box a render settles in milliseconds; on that worker, twice, it did not settle inside a second,
 * and two rendered tests went red for a reason that had nothing to do with the app — and a red
 * gate blocks a deploy.
 *
 * A timeout is a LIMIT, not a delay: a test that settles in 20 ms still takes 20 ms. So the limits
 * are raised for the whole suite. A slow machine now makes the suite slower, never red.
 *
 * `@testing-library/dom` (not `/react`) on purpose: it only sets configuration and touches no
 * `document`, so it is safe in the `node` test environment most of this suite runs in.
 */
import { configure } from '@testing-library/dom'

configure({ asyncUtilTimeout: 10_000 })

// The per-test limit must sit ABOVE the async-helper limit, or jest kills the test first and the
// failure reads as a bare timeout instead of "unable to find an element with the text …".
jest.setTimeout(30_000)
