/**
 * Asking a student WHICH gift, before the form (gift setup flow, 2026-09-06).
 *
 * ⚠ THIS IS PF-1'S REFUSAL MOVED EARLIER — NOT A RELAXATION OF IT. `resolve_open_cohort` still
 * refuses to guess between two open rounds, because guessing once filed a student under the wrong
 * foundation, funded from the wrong money, with no error anywhere. What changed is WHEN that
 * refusal reaches the student: it used to arrive as a 409 AFTER the whole form was filled in.
 *
 * Newly reachable at all because the owner's per-gift ruling (2026-09-06) lets one organisation
 * run two open rounds; until then two open rounds meant two tenants.
 */
import { needsProgrammeChoice, setApplyProgramme, rememberApplyProgramme, APPLY_PROGRAMME_KEY }
  from '@/lib/scholarship'

const store = () => {
  const m = new Map<string, string>()
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => { m.set(k, v) },
    removeItem: (k: string) => { m.delete(k) },
    _map: m,
  }
}

describe('when a student must be asked which programme', () => {
  const two = [{ code: 'a' }, { code: 'b' }]

  it('asks only when nothing is remembered AND the server offered a choice', () => {
    expect(needsProgrammeChoice('', two)).toBe(true)
  })

  it('⚠ never asks somebody who followed an organisation\'s own link', () => {
    // They already told us, by arriving on `?p=`. Asking again would be the screen doubting a
    // fact it holds — and it is the same value either way, so there is nothing to resolve.
    expect(needsProgrammeChoice('brightpath-flagship', two)).toBe(false)
  })

  it('⚠ never asks when there is only one open round — today, and the common case for ever', () => {
    expect(needsProgrammeChoice('', [{ code: 'only' }])).toBe(false)
    expect(needsProgrammeChoice('', [])).toBe(false)
    expect(needsProgrammeChoice('', undefined)).toBe(false)
  })

  it('treats whitespace as nothing remembered, not as an answer', () => {
    expect(needsProgrammeChoice('   ', two)).toBe(true)
  })
})

describe('a chosen programme travels the same road as a linked one', () => {
  it('⚠ writes THE SAME KEY a `?p=` link writes, so submit cannot tell them apart', () => {
    // The whole safety argument rests on this: one routing path to be right about, not two.
    const s = store()
    setApplyProgramme('sabah', s)
    expect(s.getItem(APPLY_PROGRAMME_KEY)).toBe('sabah')
    expect(rememberApplyProgramme('', s)).toBe('sabah')
  })

  it('a URL that names a programme still WINS over an earlier pick', () => {
    // The link is the more deliberate signal — the student has just followed that organisation's
    // own address — and a stale pick from an abandoned visit must not override it.
    const s = store()
    setApplyProgramme('sabah', s)
    expect(rememberApplyProgramme('?p=brightpath-flagship', s)).toBe('brightpath-flagship')
  })

  it('stores nothing for a blank pick, rather than an empty answer', () => {
    const s = store()
    setApplyProgramme('   ', s)
    expect(s.getItem(APPLY_PROGRAMME_KEY)).toBeNull()
  })
})
