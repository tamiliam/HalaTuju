/** V2a (2026-09-09): the wallet-ID box is GONE from the Vircle Action-Centre task.
 *
 *  The eWallet ID arrives via Vircle's own Airtable callback after the student confirms —
 *  typing it was the source of every wallet-id defect on record (DuitNow truncations,
 *  roll-over refusals). This is a STRUCTURAL claim (the input must not exist), so a
 *  source-shape guard is the right tool per the repo's testing note: it stops the box
 *  being restored "for completeness" without a deliberate decision. Interactive behaviour
 *  (the confirm still resolving) is covered by the backend TestConfirm suite.
 */
import fs from 'fs'
import path from 'path'

const SRC = fs.readFileSync(path.join(__dirname, 'ActionCentre.tsx'), 'utf8')

describe('V2a: the Vircle task asks for the mobile only', () => {
  it('has no wallet-ID input', () => {
    expect(SRC).not.toContain('vircle-id')
    expect(SRC).not.toContain('walletId')
    expect(SRC).not.toContain('VIRCLE_PREFIX')
    expect(SRC).not.toContain('SUFFIX_LEN')
  })

  it('does not send a vircle_id from the confirm', () => {
    // resolveResolutionItem's 5th argument was the assembled id; the confirm now passes
    // only (id, mobile, { token }).
    expect(SRC).not.toContain('errorDuitnow')
  })

  it('still keeps the mobile field and the confirm', () => {
    expect(SRC).toContain('formatMyMobile')
    expect(SRC).toContain('localMobileDigits')
    expect(SRC).toContain("t('scholarship.actionCentre.vircle.confirm')")
  })
})

describe('V2a: the retired wallet-ID strings are gone from all three locales', () => {
  for (const locale of ['en', 'ms', 'ta'] as const) {
    it(`${locale}.json carries no walletId/errorDuitnow keys`, () => {
      const messages = fs.readFileSync(
        path.join(__dirname, '..', 'messages', `${locale}.json`), 'utf8')
      expect(messages).not.toContain('"walletId"')
      expect(messages).not.toContain('"walletIdHint"')
      expect(messages).not.toContain('"walletIdEcho"')
      expect(messages).not.toContain('"walletIdCheck"')
      expect(messages).not.toContain('"errorDuitnow"')
    })
  }
})
