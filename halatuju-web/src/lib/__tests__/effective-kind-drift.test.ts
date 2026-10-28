/**
 * Guardrail: the front end's `effectiveKind` must resolve a request's kind the same way the
 * server does, because that answer decides whether the organisation is CHARGED.
 *
 * Why this file exists. On 2026-10-29 the owner opened request 5, read "Bug report" on it and
 * reasonably concluded the work was free — bug fixing is paid for by the 15% development margin.
 * It was being billed as a feature. The pill printed `kind` (what the organisation FILED) while
 * the money came from `triaged_kind` (what triage ADJUDICATED), and nothing on the page said the
 * two disagreed. `effectiveKind` was added so one rule answers both, and this pins it against the
 * server rather than trusting a comment to keep them in step.
 *
 * There are THREE copies of the rule on the server side and all three are read here:
 *   - `org_requests._effective_kind`  — the service's gate (quote / schedule actions)
 *   - `platform_cost.billable_kind`   — re-exported from `request_hours.billable_kind`, the one
 *                                        that sets the price
 *   - the FE `effectiveKind`          — what a reader sees
 *
 * Like `soft-evidence-drift.test.ts`, this sanity-checks its own parse so a refactor that stops
 * matching cannot quietly turn the file into a 0-assert no-op.
 */
import { effectiveKind, filedKindDiffers } from '@/lib/requestStatus'
import { readApi } from '@/test/apiSource'

// ⚠ Repo-relative literals through `readApi`, never a hand-rolled path join (TD-276): it fails by
// NAME when a module moves, and the api's own `test_web_guards_read_live_paths.py` extracts these
// literals so a backend sprint that moves either file goes red in its OWN gate.
const SERVICE = 'apps/scholarship/org_requests.py'
const BILLING = 'apps/scholarship/request_hours.py'

/**
 * The body of one server function, normalised so `req.triaged_kind` and `row['triaged_kind']`
 * read the same.
 *
 * ⚠ The WHOLE BODY, not the first `return` after the `def`. The first attempt at this test matched
 * one return line and silently captured `return 'feature'` — the early exit for a row with no
 * request behind it — and then failed claiming the rule had changed. A parse that can grab the
 * wrong line is worse than no parse: it reports a drift that is not there.
 */
function functionBody(source: string, name: string): string {
  const src = readApi(source)
  const start = src.indexOf(`def ${name}(`)
  expect(start).toBeGreaterThan(-1)
  const after = src.slice(start)
  const next = after.slice(1).search(/\ndef \w/)
  return (next === -1 ? after : after.slice(0, next + 1))
    .replace(/\breq\.|\brow\[['"]|['"]\]/g, '')
    .replace(/\s+/g, ' ')
}

describe('effectiveKind mirrors the server (the rule that decides the money)', () => {
  test('the service resolver is still `triaged_kind or kind` (parse sanity + the rule)', () => {
    const body = functionBody(SERVICE, '_effective_kind')
    expect(body).toContain('return triaged_kind or kind')
  })

  test('the BILLING resolver reads triaged_kind first, then kind', () => {
    const body = functionBody(BILLING, 'billable_kind')
    expect(body).toContain('triaged_kind or kind')
    // ⚠ Its fallback must be FEATURE, not bug. An untriaged or unknown request stays billable; a
    // wrong default here silently makes work free, which is the opposite failure and just as bad.
    expect(body).toMatch(/triaged_kind or kind or 'feature'/)
  })

  test('the front end agrees with both, case by case', () => {
    const cases: Array<[{ kind: string; triaged_kind: string }, string]> = [
      [{ kind: 'bug', triaged_kind: 'feature' }, 'feature'],
      [{ kind: 'feature', triaged_kind: 'bug' }, 'bug'],
      [{ kind: 'bug', triaged_kind: '' }, 'bug'],
      [{ kind: 'feature', triaged_kind: '' }, 'feature'],
    ]
    for (const [req, expected] of cases) {
      // The server's rule, applied here to the same input, so the two cannot be read differently.
      expect(req.triaged_kind || req.kind).toBe(expected)
      expect(effectiveKind(req)).toBe(expected)
    }
  })

  test('a disagreement is reported exactly when the two fields hold different answers', () => {
    expect(filedKindDiffers({ kind: 'bug', triaged_kind: 'feature' })).toBe(true)
    expect(filedKindDiffers({ kind: 'bug', triaged_kind: 'bug' })).toBe(false)
    expect(filedKindDiffers({ kind: 'bug', triaged_kind: '' })).toBe(false)
  })

  test('the server still treats a BUG as free, so the mirror is worth having', () => {
    // If this ever stops being true, the whole reason the kind decides money has changed and this
    // file's premise needs re-reading rather than its assertions being adjusted.
    // Backticks allowed: the docstring writes the values as ``'feature'`` (priced) / ``'bug'``.
    const src = readApi(BILLING)
    expect(src).toMatch(/'feature'`*\s*\(priced\)[\s\S]*?'bug'`*\s*\(free\)/)
  })
})
