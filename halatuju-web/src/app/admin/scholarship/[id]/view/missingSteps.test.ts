/**
 * #81 (27 Nov 2026): the "not sent to QC" line names the missing step. Owner ruling 28 Nov: the list is
 * the server's hand-off `missing` (read through `handoffMissing`), never every false completeness part.
 */
import en from '@/messages/en.json'
import { handoffMissing } from '@/lib/handoff'

import { missingStepKeys, notSubmittedIncompleteText } from './missingSteps'

/** A translator over the real English catalogue, with `{param}` filled in. */
const t = (key: string, params?: Record<string, string>) => {
  const raw = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], en)
  if (typeof raw !== 'string') throw new Error(`no English text for ${key}`)
  return raw.replace(/\{(\w+)\}/g, (_, p: string) => params?.[p] ?? `{${p}}`)
}

const ALL_PARTS = [
  'quiz_done', 'details_done', 'funding_done', 'documents_done', 'consent_done',
  'address_done', 'guardian_docs_done', 'family_done',
]

describe('#81: the missing step is named', () => {
  it('an early case missing only the quiz says so', () => {
    expect(notSubmittedIncompleteText(t, ['quiz_done'], 'en'))
      .toBe('Assessment saved, but NOT sent to QC — still missing: the interest quiz.')
  })

  it('two steps are joined the way English does it, in the student order', () => {
    expect(notSubmittedIncompleteText(t, ['consent_done', 'quiz_done'], 'en'))
      .toBe('Assessment saved, but NOT sent to QC — still missing: the interest quiz and the consent form.')
  })

  it('every completeness step has English words', () => {
    const keys = missingStepKeys(ALL_PARTS)
    expect(keys).toHaveLength(8)
    for (const k of keys) expect(t(k)).not.toBe('')
  })

  it('an unknown key is not listed, and nothing named falls back to the general line', () => {
    expect(missingStepKeys(['complete'])).toEqual([])
    expect(missingStepKeys(null)).toEqual([])
    expect(missingStepKeys([])).toEqual([])
    expect(notSubmittedIncompleteText(t, [], 'en')).toBe(t('admin.scholarship.decision.notSubmittedIncomplete'))
  })
})

describe('owner 28 Nov: the line lists ONLY the hand-off parts', () => {
  it('a late case with the quiz gone AND consent missing names only the consent', () => {
    const d = {
      completeness: {
        quiz_done: false, details_done: false, funding_done: true, documents_done: true, consent_done: false,
        address_done: true, guardian_docs_done: true, family_done: true, complete: false,
      },
      handoff: { ready: false, missing: ['consent_done'] },
    }
    expect(notSubmittedIncompleteText(t, handoffMissing(d), 'en'))
      .toBe('Assessment saved, but NOT sent to QC — still missing: the consent form.')
  })
})
