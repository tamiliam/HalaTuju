/**
 * The Recommendation panel must not lock on a HALF-COMPLETED Approve.
 *
 * ⚠ WHY A SOURCE GUARD AND NOT A RENDERED TEST. The house rule is that interactive state needs a
 * rendered test, and it is the right rule — but the officer cockpit has no test harness (mounting
 * it is the deferred `AdminApplicationDetail` fixture work), and this claim is STRUCTURAL: one
 * expression either consults `isStuckAfterVerdict` or it does not. The BEHAVIOUR the expression
 * feeds is tested purely in `officerCockpit.test.ts`; what this pins is that the page still asks.
 *
 * ⚠ AND THERE IS NO LIVE CASE LEFT TO EYEBALL. Application 144, the one that was stranded, was
 * advanced by hand on 2026-09-07, so it now renders the normal locked panel. The next case to
 * reach this state will be a real student, discovered the same way the last one was — by someone
 * noticing. That is precisely why the guard is worth its few lines.
 *
 * The trap: one Approve press saves the verdict, THEN submits the case. Saving the verdict sets
 * `verdict_decided_at`, and that is what makes the panel read-only — so a second half that does
 * not run leaves the reviewer with no button. The only exit was Reopen: super-only, and recorded
 * as a correction against a reviewer who did nothing wrong. (BrightPath #21.)
 */
import fs from 'fs'
import path from 'path'

const VIEW = path.join(process.cwd(), 'src/app/admin/scholarship/[id]/view.tsx')

/** The file with `//` line comments stripped, so a guard can never pass on its own documentation. */
function code(): string {
  return fs.readFileSync(VIEW, 'utf8')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
    .join('\n')
}

describe('the Approve lock-out cannot come back', () => {
  it('the cockpit imports the rule', () => {
    expect(code()).toContain('isStuckAfterVerdict')
  })

  it('decisionLocked is computed WITH the stuck check', () => {
    const src = code()
    const line = src.split('\n').find((l) => l.includes('const decisionLocked'))
    expect(line).toBeTruthy()
    // Whatever else it says, it must exempt a case whose Approve only half-ran.
    expect(line).toContain('!stuckAfterVerdict')
  })

  it('the stuck state is derived from verified_at, not from the status alone', () => {
    // Keying on the status would unlock a case that moved on and came back; `verified_at` is the
    // record of whether the accept ever ran. Pinned here because the two look interchangeable.
    const src = code()
    const at = src.indexOf('isStuckAfterVerdict({')
    expect(at).toBeGreaterThan(-1)
    expect(src.slice(at, at + 220)).toContain('verifiedAt: app.verified_at')
  })

  it('a reviewer coming back is TOLD the verdict is already saved', () => {
    // Without the note the panel looks untouched on a fresh load, so she cannot tell whether her
    // decision was recorded — the only clue she ever had vanished with the page.
    expect(code()).toContain('recordVerdict.savedNotSubmitted')
  })
})
