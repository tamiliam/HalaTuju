/**
 * @jest-environment jsdom
 *
 * Pre-U sprint (2026-11-26): the Angka Giliran shapes, the pre-U field's show rule / first chip /
 * STPM prefill, the STPM-to-SPM switch flag flow, and the i18n keys in all three locales.
 */
import { ANGKA_GILIRAN_MAX, isValidAngkaGiliran, normaliseAngkaGiliran } from '@/lib/angkaGiliran'
import { preUStudiedAtPrefill, showsPreUStudiedAt } from '@/lib/preUStudiedAt'
import { firstPreURoute } from '@/lib/preULists'
import {
  CONFIRM_TTL_MS, applyHeldClear, confirmSpmSwitch, dropLocalHeldResults, forgetSpmSwitch, heldResultsSummary,
  markSpmSaved, needsSpmSwitchDialog, restoreAfterRefusedClear, serverHoldsSpmOnly, settleHeldClear,
} from '@/lib/resultsSwitch'
import { markTertiaryCompleted } from '@/lib/heldResultsLocal'
import { resultsSyncFields, signInResultsFields, syncProfileSafely } from '@/lib/resultsSync'
import * as api from '@/lib/api'
import type { SyncProfileData } from '@/lib/api'
import {
  KEY_CLEAR_HELD_PENDING, KEY_EXAM_TYPE, KEY_HIGHER_CGPA, KEY_RESULTS_COMPLETED_AT, KEY_RESULTS_EXAM_TYPE,
  KEY_STPM_CGPA, KEY_STPM_GRADES,
} from '@/lib/storage'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/api', () => ({ ...jest.requireActual('@/lib/api'), syncProfile: jest.fn() }))

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); jest.clearAllMocks() })

describe('Angka Giliran', () => {
  it('accepts the SPM and the STPM shapes, and a blank', () => {
    expect(isValidAngkaGiliran('AB123C456')).toBe(true)
    expect(isValidAngkaGiliran('AB1234/5678')).toBe(true)
    expect(isValidAngkaGiliran('ab 1234/5678')).toBe(true)
    expect(isValidAngkaGiliran('')).toBe(true)
  })
  it('refuses anything else', () => {
    for (const bad of ['AB12C456', 'AB1234-5678', 'AB12345678', 'AB123/5678', 'A1234/5678', 'AB123C4567'])
      expect(isValidAngkaGiliran(bad)).toBe(false)
  })
  it('normalises to upper case without spaces and cuts to 11', () => {
    expect(normaliseAngkaGiliran(' ab 1234 / 5678 ')).toBe('AB1234/5678')
    expect(normaliseAngkaGiliran('ab123c456789xyz')).toHaveLength(ANGKA_GILIRAN_MAX)
    expect(ANGKA_GILIRAN_MAX).toBe(11)
  })
})

describe('pre-U field rules', () => {
  it('shows only for STPM, Matriculation, Asasi or Diploma', () => {
    for (const r of ['stpm', 'matric', 'asasi', 'diploma']) expect(showsPreUStudiedAt(r)).toBe(true)
    for (const r of ['spm', '', null, undefined, 'other']) expect(showsPreUStudiedAt(r)).toBe(false)
  })
  it('opens the chip that follows their results', () => {
    expect(firstPreURoute('stpm')).toBe('form6')
    expect(firstPreURoute('matric')).toBe('matric')
    expect(firstPreURoute('asasi')).toBe('university')
    expect(firstPreURoute('diploma')).toBe('poly')
  })
  it('prefills from the attended Form 6 school for STPM only (TD-734)', () => {
    expect(preUStudiedAtPrefill({ results_held: 'stpm', pre_u_institution: 'SMK Seri Puteri' })).toBe('SMK Seri Puteri')
    expect(preUStudiedAtPrefill({ results_held: 'matric', pre_u_institution: 'KM Johor' })).toBe('')
    expect(preUStudiedAtPrefill({ results_held: 'stpm', pre_u_studied_at: 'SMK A', pre_u_institution: 'SMK B' })).toBe('SMK A')
    expect(preUStudiedAtPrefill(null)).toBe('')
  })
})

describe('STPM-to-SPM switch', () => {
  const payload = (): SyncProfileData => ({ stpm_grades: { pa: 'A' }, stpm_cgpa: 3.42, higher_cgpa: 3.1, grades: { bm: 'A' } } as SyncProfileData)

  it('asks only a student the server says holds tertiary results', () => {
    expect(needsSpmSwitchDialog({ results_held: 'stpm' })).toBe(true)
    expect(needsSpmSwitchDialog({ results_held: 'diploma' })).toBe(true)
    expect(needsSpmSwitchDialog({ results_held: 'spm' })).toBe(false)
    expect(needsSpmSwitchDialog(null)).toBe(false)
  })
  it('summarises the held results for the dialog', () => {
    expect(heldResultsSummary({ results_held: 'stpm', stpm_cgpa: 3.42 }, (k) => k)).toEqual({ route: 'STPM', summary: 'STPM PNGK 3.42' })
    expect(heldResultsSummary({ results_held: 'matric', higher_cgpa: 3.9 }, () => 'Matriculation'))
      .toEqual({ route: 'Matriculation', summary: 'Matriculation CGPA 3.90' })
  })
  // Review round 1: the flag lives in sessionStorage (flagStore), the results in localStorage.
  it('sends no clear without a confirmed switch AND a saved SPM form', () => {
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    const p = payload()
    expect(applyHeldClear(p, sessionStorage, localStorage)).toBe(false)   // no dialog yes
    expect(p.clear_held_results).toBeUndefined()
    confirmSpmSwitch(sessionStorage)
    expect(applyHeldClear(p, sessionStorage, localStorage)).toBe(false)   // yes, but the grades not saved
    markSpmSaved(sessionStorage)
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
    expect(applyHeldClear(p, sessionStorage, localStorage)).toBe(false)   // ready, but the completion is not SPM
    expect(p.stpm_cgpa).toBe(3.42)
  })
  it('sends the clear, without the STPM fields, once confirmed and saved', () => {
    confirmSpmSwitch(sessionStorage)
    markSpmSaved(sessionStorage)
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    const p = payload()
    expect(applyHeldClear(p, sessionStorage, localStorage)).toBe(true)
    expect(p.clear_held_results).toBe(true)
    expect(p.stpm_grades).toBeUndefined()
    expect(p.stpm_cgpa).toBeUndefined()
    expect(p.higher_cgpa).toBeUndefined()
    expect(p.grades).toEqual({ bm: 'A' })
  })
  it('keeps the flag in sessionStorage only, never localStorage', () => {
    confirmSpmSwitch(sessionStorage)
    expect(localStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
    expect(JSON.parse(sessionStorage.getItem(KEY_CLEAR_HELD_PENDING) as string).state).toBe('confirmed')
    // An old localStorage flag (the earlier build) is never read.
    sessionStorage.clear()
    localStorage.setItem(KEY_CLEAR_HELD_PENDING, 'ready')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    expect(applyHeldClear(payload(), sessionStorage, localStorage)).toBe(false)
  })
  it('a yes older than 30 minutes is not honoured: a later grades save sends no clear', () => {
    const t0 = 1_000_000
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    confirmSpmSwitch(sessionStorage, t0)
    markSpmSaved(sessionStorage, t0 + CONFIRM_TTL_MS + 1)               // the save comes too late
    expect(sessionStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
    expect(applyHeldClear(payload(), sessionStorage, localStorage, t0 + CONFIRM_TTL_MS + 2)).toBe(false)
  })
  it('a ready flag also expires 30 minutes after the yes', () => {
    const t0 = 2_000_000
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    confirmSpmSwitch(sessionStorage, t0)
    markSpmSaved(sessionStorage, t0 + 60_000)
    expect(applyHeldClear(payload(), sessionStorage, localStorage, t0 + CONFIRM_TTL_MS - 1)).toBe(true)
    expect(applyHeldClear(payload(), sessionStorage, localStorage, t0 + CONFIRM_TTL_MS + 1)).toBe(false)
  })
  it('a malformed flag is ignored', () => {
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    sessionStorage.setItem(KEY_CLEAR_HELD_PENDING, 'ready')
    expect(applyHeldClear(payload(), sessionStorage, localStorage)).toBe(false)
  })
  it('an SPM save with no confirmed switch records nothing', () => {
    markSpmSaved(sessionStorage)
    expect(sessionStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
  })
  it('Back (or another route) forgets the switch', () => {
    confirmSpmSwitch(sessionStorage)
    forgetSpmSwitch(sessionStorage)
    markSpmSaved(sessionStorage)
    expect(sessionStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
  })
  it('settle removes the local STPM keys only when the server took the clear', () => {
    localStorage.setItem(KEY_STPM_GRADES, '{"pa":"A"}')
    localStorage.setItem(KEY_STPM_CGPA, '3.42')
    localStorage.setItem(KEY_HIGHER_CGPA, '3.1')
    confirmSpmSwitch(sessionStorage)
    settleHeldClear(sessionStorage, localStorage, false)
    expect(localStorage.getItem(KEY_STPM_GRADES)).not.toBeNull()
    expect(sessionStorage.getItem(KEY_CLEAR_HELD_PENDING)).toBeNull()
    settleHeldClear(sessionStorage, localStorage, true)
    expect(localStorage.getItem(KEY_STPM_GRADES)).toBeNull()
    expect(localStorage.getItem(KEY_STPM_CGPA)).toBeNull()
    expect(localStorage.getItem(KEY_HIGHER_CGPA)).toBeNull()
  })
  it('a refused clear puts this browser back on the results the server still holds', () => {
    localStorage.setItem(KEY_EXAM_TYPE, 'spm')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    localStorage.setItem(KEY_STPM_GRADES, '{"pa":"A"}')
    restoreAfterRefusedClear(localStorage, 'stpm')
    expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe('stpm')
    expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('stpm')
    expect(localStorage.getItem(KEY_STPM_GRADES)).toBe('{"pa":"A"}')
    restoreAfterRefusedClear(localStorage, 'spm')                          // never "restores" to SPM
    expect(localStorage.getItem(KEY_EXAM_TYPE)).toBe('stpm')
  })
  it('reads an SPM-only server profile (the state the switch leaves) for the hydrate clear', () => {
    const spmOnly = { results_held: 'spm', completed_qualifications: ['spm'], stpm_grades: {} }
    expect(serverHoldsSpmOnly(spmOnly)).toBe(true)
    expect(serverHoldsSpmOnly({ ...spmOnly, stpm_cgpa: 3.4 })).toBe(false)
    expect(serverHoldsSpmOnly({ ...spmOnly, higher_cgpa: 3.1 })).toBe(false)
    expect(serverHoldsSpmOnly({ ...spmOnly, stpm_grades: { pa: 'A' } })).toBe(false)
    expect(serverHoldsSpmOnly({ ...spmOnly, completed_qualifications: [] })).toBe(false)   // nothing completed yet
    expect(serverHoldsSpmOnly({ results_held: 'stpm', completed_qualifications: ['spm', 'stpm'] })).toBe(false)
    expect(serverHoldsSpmOnly(null)).toBe(false)
    localStorage.setItem(KEY_STPM_GRADES, '{"pa":"A"}')
    localStorage.setItem(KEY_HIGHER_CGPA, '3.1')
    dropLocalHeldResults(localStorage)
    expect(localStorage.getItem(KEY_STPM_GRADES)).toBeNull()
    expect(localStorage.getItem(KEY_HIGHER_CGPA)).toBeNull()
  })
  it('the onboarding door sends a tertiary completion with its time, and never an SPM one', () => {
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
    markTertiaryCompleted(localStorage)
    const at = localStorage.getItem(KEY_RESULTS_COMPLETED_AT) as string
    expect(Number.isNaN(Date.parse(at))).toBe(false)
    expect(resultsSyncFields(localStorage)).toMatchObject({ results_exam_type: 'stpm', results_completed_at: at })
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    expect('results_completed_at' in resultsSyncFields(localStorage)).toBe(false)
  })
  it('the sign-in door never carries the clear, even with a ready flag', () => {
    confirmSpmSwitch(sessionStorage)
    markSpmSaved(sessionStorage)
    localStorage.setItem(KEY_EXAM_TYPE, 'spm')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
    const out = signInResultsFields(localStorage, { results_exam_type: '', completed_qualifications: [] })
    expect('clear_held_results' in out).toBe(false)
  })
  it('a locked refusal drops the clear from the payload and resends the rest', async () => {
    const sync = api.syncProfile as jest.Mock
    sync.mockRejectedValueOnce(Object.assign(new Error('400'), {
      status: 400, fieldErrors: { clear_held_results: ['Your application uses the results you hold.'] },
    })).mockResolvedValueOnce({})
    const p = { grades: { bm: 'A' }, clear_held_results: true } as SyncProfileData
    await syncProfileSafely(p, { token: 't' })
    expect(sync).toHaveBeenCalledTimes(2)
    expect(p.clear_held_results).toBeUndefined()
    expect(sync.mock.calls[1][0]).toEqual({ grades: { bm: 'A' } })
  })
  it('any other failure is thrown as before', async () => {
    const sync = api.syncProfile as jest.Mock
    sync.mockRejectedValueOnce(Object.assign(new Error('500'), { status: 500 }))
    await expect(syncProfileSafely({ clear_held_results: true } as SyncProfileData, { token: 't' })).rejects.toThrow('500')
    expect(sync).toHaveBeenCalledTimes(1)
  })
})

describe('i18n keys exist in en, ms and ta', () => {
  const KEYS = [
    'onboarding.school', 'onboarding.switchSpmTitle', 'onboarding.switchSpmHeld', 'onboarding.switchSpmRemove',
    'onboarding.switchSpmNothing', 'onboarding.switchSpmConfirm', 'onboarding.switchSpmLocked',
    'scholarship.preU.label', 'scholarship.preU.tipApply.stpm', 'scholarship.preU.tipApply.matric',
    'scholarship.preU.tipApply.asasi', 'scholarship.preU.tipApply.diploma', 'scholarship.preU.tipProfile',
    'scholarship.preU.chip.form6', 'scholarship.preU.chip.matric', 'scholarship.preU.chip.university',
    'scholarship.preU.chip.poly', 'scholarship.preU.placeholder', 'scholarship.preU.useAsTyped',
    'scholarship.apply.error.preUStudiedAt', 'scholarship.apply.field.school', 'scholarship.apply.tip.school',
    'profile.angkaGiliranHelper', 'profile.angkaGiliranInvalid', 'admin.scholarship.preUStudiedAt',
  ]
  const get = (o: unknown, k: string) => k.split('.').reduce<unknown>((a, p) => (a as Record<string, unknown>)?.[p], o)
  it.each([['en', en], ['ms', ms], ['ta', ta]])('%s', (_loc, m) => {
    for (const k of KEYS) expect([k, typeof get(m, k)]).toEqual([k, 'string'])
  })
  it('uses the new wording in English', () => {
    expect(get(en, 'onboarding.school')).toBe('Secondary School')
    expect(get(en, 'scholarship.apply.field.school')).toBe('Secondary School')
    expect(get(en, 'scholarship.apply.tip.school')).toBe('The secondary school where you sat for SPM.')
    expect(get(en, 'onboarding.switchSpmTitle')).toBe('Switch to SPM results?')
    // Review round 1: a closed (maybe awarded) application locks the switch too, and the copy says so.
    expect(get(en, 'onboarding.switchSpmLocked')).toContain('open, closed or awarded')
  })
})
