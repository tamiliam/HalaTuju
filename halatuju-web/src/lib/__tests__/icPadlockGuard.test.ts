/**
 * Static guard: the IC padlock must be driven by the LOCK, never hard-coded (2026-07-29).
 *
 * Why a source guard rather than a render test. The defect this replaces was not a wrong value
 * flowing through a component — it was `disabled` written as a bare HTML attribute, with a
 * padlock icon beside it that had no condition at all. It shipped the day the field was built
 * and survived every review since, telling 85 of 143 production applicants their IC was locked
 * when nothing had locked it. A render test proves the current wiring works; this proves nobody
 * has quietly gone back to a constant. Same family as the org-fence static guard and the
 * brand-colour guard.
 *
 * What it does NOT prove: that the field looks right, or that the flag panel reads well. Those
 * are for a human — the copy deliberately declines to say which side is wrong.
 */
import { readFileSync } from 'fs'
import { join } from 'path'

const PAGE = join(process.cwd(), 'src', 'app', 'profile', 'page.tsx')
const src = readFileSync(PAGE, 'utf8')

/** The IC input, from its `type="text"` through to the closing brace of its className. */
function icInputBlock(): string {
  const anchor = src.indexOf("aria-label={t('profile.icMasked')}")
  expect(anchor).toBeGreaterThan(-1)   // the field moved or lost its label — re-point this guard
  return src.slice(anchor - 700, anchor + 700)
}

describe('the IC field is gated by the stored lock', () => {
  it('never disables the input with a bare attribute', () => {
    const block = icInputBlock()
    // `disabled` alone (not `disabled={...}`) is the original bug, verbatim.
    expect(block).not.toMatch(/\n\s*disabled\s*\n/)
    expect(block).toMatch(/disabled=\{!icEditable\}/)
  })

  it('derives editability from nric_locked and nothing else', () => {
    // canEditIc reads only the stored lock. If someone swaps in identityVerified — which is
    // broader AND re-derived on every read — students lock with no genuineness check and
    // unlock again by deleting their card.
    expect(src).toMatch(/const icEditable = canEditIc\(\{ nric_locked: nricLocked \}\)/)
    expect(src).not.toMatch(/canEditIc\(\{[^}]*identity_verified/)
    expect(src).not.toMatch(/disabled=\{!?identityVerified\}/)
  })

  it('draws the padlock only when the IC is actually locked', () => {
    // Both sites: the edit panel and the read-only summary row. Each padlock must sit inside
    // an `!icEditable` conditional, so the count of conditionals matches the count of locks.
    const padlocks = src.match(/M16\.5 10\.5V6\.75a4\.5 4\.5 0 1 0-9 0v3\.75/g) || []
    expect(padlocks.length).toBe(2)
    expect((src.match(/\{!icEditable && \(/g) || []).length).toBe(padlocks.length)
  })

  it('formats the loaded number before putting it in the editable box', () => {
    // 11 production profiles store the IC with no dashes (050202022022), so the raw value
    // renders as a wall of digits. formatIc is a no-op on the properly formatted rows.
    expect(src).toMatch(/setNricDraft\(formatIc\(profileData\.nric \|\| ''\)\)/)
    expect(src).not.toMatch(/setNricDraft\(profileData\.nric \|\| ''\)/)
  })

  it('never renders the mask into an editable box', () => {
    // Enabling the old field as-is would have let a student edit '****-**-2022' and submit
    // asterisks. The editable branch must show the raw draft.
    expect(icInputBlock()).toMatch(/value=\{icEditable\s*\n?\s*\?\s*nricDraft/)
  })
})

describe('the IC saves through the validated claim path', () => {
  it('uses claimNric, not the profile PUT', () => {
    // updateProfile strips nric read-only on purpose. Without this the student types, presses
    // Save, sees it succeed, and nothing changes.
    expect(src).toMatch(/claimNric\(nricDraft, false, \{ token \}\)/)
  })

  it('never sends confirm:true', () => {
    // confirm:true does not re-point a record — it moves the primary key in raw SQL and
    // re-parents saved courses, outcomes, reports and email verifications. That is an account
    // takeover, and it belongs to the sign-in prompt, never to a profile edit.
    expect(src).not.toMatch(/claimNric\([^)]*true\s*,/)
    expect(src).not.toMatch(/claimNric\([^)]*confirm:\s*true/)
  })

  it('treats a number owned by someone else as a refusal', () => {
    expect(src).toMatch(/res\.status === 'exists'/)
    expect(src).toMatch(/profile\.icTaken/)
  })
})
