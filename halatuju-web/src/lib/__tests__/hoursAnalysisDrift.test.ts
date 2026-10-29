/**
 * Guardrail: `requestStatus.hoursAnalysisId` must keep mirroring the server's
 * `request_hours.closing_report` — the rule that decides WHICH analysis the invoice reads.
 *
 * Why this exists. The hours panel is rendered once, under the quote, and it writes to the
 * analysis this helper picks. The server bills the analysis `closing_report` picks. If the two
 * rules drift, the screen cheerfully offers to edit a number the invoice does not read, and
 * nothing anywhere fails — the figures are saved, the page refreshes, and the month is still
 * billed on a different row. That is the quietest kind of money bug this codebase can have.
 *
 * I had written "mirrors the server" in a comment and left it at that. The web code-standards
 * guard caught it and said the thing worth repeating: *a comment asking two files to stay in step
 * is a request; only a test is a rule.* (2026-10-30)
 *
 * It pins the rule in BOTH directions, by reading the Python source:
 *   - the server filters on approved / not superseded / charged_hours is not None, and
 *   - it orders on (approved_at, id) and takes the MAX,
 *   - and this helper does the same three things, proven by behaviour rather than by text.
 *
 * Like the other drift tests it sanity-checks its own parse, so a refactor that stops matching
 * cannot silently turn it into a 0-assert no-op.
 */
import { hoursAnalysisId } from '@/lib/requestStatus'
import { readApi } from '@/test/apiSource'

// ⚠ A repo-relative literal through `readApi`, never a hand-rolled path (TD-276): it throws a
// NAMED failure when the module moves instead of an ENOENT that reads as a broken test, and the
// api's own `test_web_guards_read_live_paths.py` extracts this literal, so a backend sprint that
// moves the file goes red in ITS gate rather than killing this one silently.
const HOURS = 'apps/scholarship/request_hours.py'

function closingReportBody(): string {
  const src = readApi(HOURS)
  const start = src.indexOf('def closing_report(')
  expect(start).toBeGreaterThan(-1)
  const after = src.slice(start)
  const end = after.indexOf('\ndef ', 1)
  return end === -1 ? after : after.slice(0, end)
}

describe('hoursAnalysisId mirrors the server rule for the closing report', () => {
  const body = closingReportBody()

  test('the server parse found a body worth checking (parse sanity)', () => {
    // A 0-match parse would make every assertion below vacuously true.
    expect(body.length).toBeGreaterThan(200)
    expect(body).toContain('req.analyses.all()')
  })

  test('the server still filters on approved, not superseded, and a charged figure', () => {
    expect(body).toContain('a.approved_at')
    expect(body).toContain('not a.superseded_at')
    expect(body).toContain('a.charged_hours is not None')
  })

  test('the server still takes the MAX by (approved_at, id)', () => {
    expect(body).toContain('max(rows, key=lambda a: (a.approved_at, a.id))')
  })

  test('the server still answers None when nothing carries a figure', () => {
    expect(body).toContain('return None')
  })

  // ── and the web helper does the same three things ──────────────────────────
  const row = (id: number, over: Record<string, unknown> = {}) => ({
    id, approved_at: `2026-10-0${id}T00:00:00Z`, superseded_at: null,
    charged_hours: null as string | null, ...over,
  })

  test('it skips a draft and a superseded analysis, as the server does', () => {
    const draft = { ...row(2), approved_at: null }
    const superseded = row(3, { superseded_at: 'x', charged_hours: '9.0' })
    expect(hoursAnalysisId([row(1, { charged_hours: '4.0' }), draft, superseded])).toBe(1)
  })

  test('it prefers the latest row CARRYING a figure, as the server does', () => {
    expect(hoursAnalysisId([row(1, { charged_hours: '4.0' }), row(2)])).toBe(1)
  })

  test('it treats a recorded 0.0 as a figure, as the server does', () => {
    // ⚠ `charged_hours is not None` on the server — NOT a truthiness test. Request 14's
    // "none of it is charged" is 0.0, and a falsy check would drop it on the web side only.
    expect(hoursAnalysisId([row(1, { charged_hours: '0.0' }), row(2)])).toBe(1)
  })

  test('ONE thing it does that the server does not, deliberately', () => {
    // The server answers None when no row carries a figure — it is asking "what does the invoice
    // read?". The screen must still offer somewhere to type the FIRST figure, so it falls to the
    // newest approved analysis. This asymmetry is the one difference, and it is tested so that a
    // future reader does not "fix" it into agreement.
    expect(hoursAnalysisId([row(1), row(2)])).toBe(2)
  })
})
