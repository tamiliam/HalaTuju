/** @jest-environment jsdom */
/**
 * THE APPLY DRAFT (Mobile M4, owner ruling: this tab only). What it may hold, who may read it back,
 * and when it goes. The page-level behaviour (restored after a remount, cleared on submit) is in
 * `app/scholarship/apply/page.draft.test.tsx`; sign-out's wipe in `studentSignOut.test.ts`.
 * Storage is this tab's (jsdom's sessionStorage); time is jest's clock.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { act, renderHook } from '@testing-library/react'
import {
  APPLY_DRAFT_KEY, APPLY_DRAFT_MAX_AGE_MS, DRAFT_EXCLUDED, clearApplyDraft,
  readApplyDraft, useApplyDraft, writeApplyDraft,
} from '@/lib/applyDraft'
import { peekApplyDraft } from '@/lib/applyDraftPeek'
import { profileToApplyDefaults, type ApplyFormState } from '@/lib/scholarship'

const FORM: ApplyFormState = {
  ...profileToApplyDefaults(null),
  name: 'Priya', nric: '080101-14-1234', householdIncome: '2400', parentName: 'Rajan',
  parentPhone: '012-345 6789', declarationName: 'Priya', consentToContact: true,
}
const HER = { uid: 'u1', programme: 'bp' }
const NOW = 1_800_000_000_000
const raw = () => sessionStorage.getItem(APPLY_DRAFT_KEY)
const at = (ms: number) => jest.setSystemTime(ms)

beforeEach(() => {
  sessionStorage.clear()
  jest.useFakeTimers()
  at(NOW)
})
afterEach(() => { jest.useRealTimers() })

describe('what is stored', () => {
  it('never the IC, the typed signature or the consent — not even in the raw stored text', () => {
    writeApplyDraft(FORM, HER, 'family')
    const text = raw() as string
    for (const k of DRAFT_EXCLUDED) expect(text).not.toContain(`"${k}"`)
    expect(text).not.toContain('080101-14-1234')
    expect(JSON.parse(text).form.householdIncome).toBe('2400')
    expect(DRAFT_EXCLUDED).toEqual(['nric', 'declarationName', 'consentToContact'])
  })

  it('a hand-edited draft cannot smuggle an excluded field back in', () => {
    sessionStorage.setItem(APPLY_DRAFT_KEY, JSON.stringify({ v: 1, uid: 'u1', programme: 'bp', savedAt: NOW,
      step: 'support', form: { name: 'Priya', nric: '999999-99-9999', declarationName: 'X', consentToContact: true } }))
    const got = readApplyDraft(HER)?.form as Record<string, unknown>
    expect(got.name).toBe('Priya')
    for (const k of DRAFT_EXCLUDED) expect(k in got).toBe(false)
  })

  it('nothing without a signed-in user id', () => {
    writeApplyDraft(FORM, { uid: null, programme: 'bp' }, 'family')
    expect(raw()).toBeNull()
  })

  it('a full or blocked storage is swallowed — the form still works', () => {
    const spy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('QuotaExceededError') })
    expect(() => writeApplyDraft(FORM, HER, 'family')).not.toThrow()
    spy.mockRestore()
  })
})

describe('who gets it back', () => {
  it('her, for this programme, on the step she left', () => {
    writeApplyDraft(FORM, HER, 'family')
    at(NOW + 1000)
    const got = readApplyDraft(HER)
    expect(got?.step).toBe('family')
    expect(got?.form.parentPhone).toBe('012-345 6789')
  })

  it('ANOTHER user: nothing, and the draft is deleted', () => {
    writeApplyDraft(FORM, HER, 'family')
    expect(readApplyDraft({ uid: 'u2', programme: 'bp' })).toBeNull()
    expect(raw()).toBeNull()
  })

  it('no user id at all: nothing, and the draft is deleted', () => {
    writeApplyDraft(FORM, HER, 'family')
    expect(readApplyDraft({ uid: undefined, programme: 'bp' })).toBeNull()
    expect(raw()).toBeNull()
  })

  it('her, but ANOTHER programme: nothing on this form — kept for the one it was typed for', () => {
    writeApplyDraft(FORM, HER, 'family')
    expect(readApplyDraft({ uid: 'u1', programme: 'sabah' })).toBeNull()
    expect(readApplyDraft(HER)?.form.name).toBe('Priya')
  })

  it('older than 24 hours: nothing, and deleted', () => {
    writeApplyDraft(FORM, HER, 'family')
    at(NOW + APPLY_DRAFT_MAX_AGE_MS)
    expect(readApplyDraft(HER)?.form.name).toBe('Priya')
    at(NOW + APPLY_DRAFT_MAX_AGE_MS + 1)
    expect(readApplyDraft(HER)).toBeNull()
    expect(raw()).toBeNull()
  })

  it('unreadable, an unknown format, or a time in the future: nothing, and deleted', () => {
    for (const text of ['{not json', 'null', '"x"',
      JSON.stringify({ v: 2, uid: 'u1', programme: 'bp', savedAt: NOW, step: '', form: {} }),
      JSON.stringify({ v: 1, uid: 'u1', programme: 'bp', step: '', form: {} }),
      JSON.stringify({ v: 1, uid: 'u1', programme: 'bp', savedAt: NOW + 3_600_000, step: '', form: {} })]) {
      sessionStorage.setItem(APPLY_DRAFT_KEY, text)
      expect([text, readApplyDraft(HER)]).toEqual([text, null])
      expect(raw()).toBeNull()
    }
  })

  it('the pre-M4 whole-form stash (IC and signature inside) is deleted on sight, never read', () => {
    sessionStorage.setItem('halatuju_apply_stash', JSON.stringify(FORM))
    expect(readApplyDraft(HER)).toBeNull()
    expect(sessionStorage.getItem('halatuju_apply_stash')).toBeNull()
  })

  it('the detour peek reads her draft without deleting anything, and refuses another id', () => {
    writeApplyDraft({ ...FORM, school: 'SMK Taman Desa' }, HER, 'results')
    expect(peekApplyDraft('u1')?.school).toBe('SMK Taman Desa')
    expect(peekApplyDraft('u2')).toBeNull()
    // Review F2: no user id yet (sign-in loading) is not a match — never someone else's draft.
    expect(peekApplyDraft(undefined)).toBeNull()
    expect(peekApplyDraft(null)).toBeNull()
    expect(peekApplyDraft('')).toBeNull()
    expect(raw()).not.toBeNull()
  })

  it('clearApplyDraft removes it (and any old stash)', () => {
    writeApplyDraft(FORM, HER, 'family')
    sessionStorage.setItem('halatuju_apply_stash', '{}')
    clearApplyDraft()
    expect(sessionStorage.length).toBe(0)
  })
})

describe('useApplyDraft — when it is written', () => {
  it('half a second after the last change', () => {
    renderHook(() => useApplyDraft(FORM, 'u1', 'bp', 'family', true))
    expect(raw()).toBeNull()
    act(() => { jest.advanceTimersByTime(500) })
    expect(JSON.parse(raw() as string).step).toBe('family')
  })

  it('AT ONCE when the tab is hidden or put away (the timer may never fire on iOS)', () => {
    renderHook(() => useApplyDraft(FORM, 'u1', 'bp', 'plans', true))
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(raw()).not.toBeNull()
    sessionStorage.clear()
    act(() => { window.dispatchEvent(new Event('pagehide')) })
    expect(raw()).not.toBeNull()
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })

  it('never while disabled (not yet populated, nothing changed, already sent)', () => {
    renderHook(() => useApplyDraft(FORM, 'u1', 'bp', 'family', false))
    act(() => { jest.advanceTimersByTime(2000) })
    act(() => { window.dispatchEvent(new Event('pagehide')) })
    expect(raw()).toBeNull()
  })
})

describe('it never leaves the device', () => {
  it('the draft module imports nothing that talks to the network', () => {
    const src = readFileSync(join(__dirname, '..', 'applyDraft.ts'), 'utf8')
    const imports = Array.from(src.matchAll(/from '([^']+)'/g)).map((m) => m[1])
    expect(imports.sort()).toEqual(['./applyReturn', './scholarship', 'react'])
    expect(src).toMatch(/import type \{ ApplyFormState \} from '\.\/scholarship'/)   // a type only
    expect(src).not.toMatch(/\bfetch\(|XMLHttpRequest|sendBeacon|@\/lib\/api/)
  })
})
