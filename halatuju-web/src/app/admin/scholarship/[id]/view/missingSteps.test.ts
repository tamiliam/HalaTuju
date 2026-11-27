/**
 * #81 (27 Nov 2026): the "not sent to QC" line names the missing step, read from the served completeness.
 */
import en from '@/messages/en.json'

import { missingStepKeys, notSubmittedIncompleteText } from './missingSteps'

/** A translator over the real English catalogue, with `{param}` filled in. */
const t = (key: string, params?: Record<string, string>) => {
  const raw = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], en)
  if (typeof raw !== 'string') throw new Error(`no English text for ${key}`)
  return raw.replace(/\{(\w+)\}/g, (_, p: string) => params?.[p] ?? `{${p}}`)
}

const allDone = {
  quiz_done: true, details_done: true, funding_done: true, documents_done: true, consent_done: true,
  address_done: true, guardian_docs_done: true, family_done: true, complete: true,
}

describe('#81: the missing step is named', () => {
  it('case 513 shape: only the quiz is missing, and the line says so', () => {
    const c = { ...allDone, quiz_done: false, complete: false }
    expect(notSubmittedIncompleteText(t, c, 'en'))
      .toBe('Assessment saved, but NOT sent to QC — still missing: the interest quiz.')
  })

  it('two steps are joined the way English does it', () => {
    const c = { ...allDone, quiz_done: false, consent_done: false, complete: false }
    expect(notSubmittedIncompleteText(t, c, 'en'))
      .toBe('Assessment saved, but NOT sent to QC — still missing: the interest quiz and the consent form.')
  })

  it('every completeness step has English words', () => {
    const none = Object.fromEntries(Object.keys(allDone).map((k) => [k, false]))
    const keys = missingStepKeys(none)
    expect(keys).toHaveLength(8)
    for (const k of keys) expect(t(k)).not.toBe('')
  })

  it('a key the payload does not carry is not listed, and nothing named falls back to the general line', () => {
    expect(missingStepKeys({ complete: false })).toEqual([])
    expect(missingStepKeys(null)).toEqual([])
    expect(notSubmittedIncompleteText(t, { complete: false }, 'en')).toBe(
      t('admin.scholarship.decision.notSubmittedIncomplete'))
  })
})
