/**
 * THE DRIFT TEST for `lib/profileActivity.ts` — named by its `drift-test:` marker (common profile
 * S5, 2026-10-31).
 *
 * The server's closed lists are the rule: the verbs (`StaffActivityVerb`), the subject types
 * (`StaffActivitySubject`) — both in `apps/scholarship/models/staff_activity.py` — the reader's
 * filters (`staff_activity_read.FILTERS`) and its neutral words (`staff_activity_read.NEUTRAL`).
 * Read from the api's source, never restated, and asserted BOTH ways:
 *   * every verb the server can write has a sentence in en, ms and ta — with `{subject}` exactly
 *     when the verb is about somebody (a missing one would print a raw key, or drop the subject);
 *   * every subject type has its translated neutral words (hidden, removed) in all three, and a
 *     reference type its `named` form — the card never shows the server's English word;
 *   * the web's copies of those lists are the server's, in both directions.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import {
  ACTIVITY_FILTERS, ACTIVITY_KEY, ACTIVITY_SUBJECT_TYPES, ACTIVITY_VERBS, NO_SUBJECT_VERBS, REFERENCE_TYPES,
} from '@/lib/profileActivity'
import { pySeq, readApi } from '@/test/apiSource'

const MODEL = readApi('apps/scholarship/models/staff_activity.py')
const READER = readApi('apps/scholarship/staff_activity_read.py')

/** The values of a `class NAME(models.TextChoices):` block — `MEMBER = 'value', 'Label'` lines. */
function textChoices(src: string, name: string): string[] {
  const start = src.indexOf(`class ${name}(models.TextChoices):`)
  if (start < 0) throw new Error(`drift test: no \`class ${name}(models.TextChoices)\` in the model`)
  const rest = src.slice(start).split('\n').slice(1)
  const end = rest.findIndex((l) => /^\S/.test(l))
  const body = (end < 0 ? rest : rest.slice(0, end)).join('\n')
  return [...body.matchAll(/^ {4}[A-Z][A-Z0-9_]* = '([a-z0-9_]+)'/gm)].map((m) => m[1])
}

const VERBS = textChoices(MODEL, 'StaffActivityVerb')
const SUBJECTS = textChoices(MODEL, 'StaffActivitySubject')

const resolve = (msgs: unknown, key: string): unknown =>
  key.split('.').reduce<unknown>((cur, k) => (cur && typeof cur === 'object' ? (cur as Record<string, unknown>)[k] : undefined), msgs)

describe('parse sanity — the scan found the lists', () => {
  it('43 verbs, 10 subject types', () => {
    expect(VERBS.length).toBeGreaterThanOrEqual(43)
    expect(SUBJECTS.length).toBeGreaterThanOrEqual(10)
    expect(VERBS).toContain('verdict_recorded')
    expect(SUBJECTS).toContain('application')
  })
})

describe('the web lists are the server lists', () => {
  it('verbs', () => { expect([...ACTIVITY_VERBS]).toEqual(VERBS) })
  it('subject types', () => { expect([...ACTIVITY_SUBJECT_TYPES]).toEqual(SUBJECTS) })
  it('filters (`staff_activity_read.FILTERS`)', () => {
    expect([...ACTIVITY_FILTERS]).toEqual(pySeq(READER, 'FILTERS'))
  })
  it('every neutral word the reader has is a subject type, and every subject type has one', () => {
    const m = READER.match(/^NEUTRAL = \{([\s\S]*?)^\}/m)
    if (!m) throw new Error('drift test: no `NEUTRAL = { … }` in staff_activity_read.py')
    const keys = [...m[1].matchAll(/^ {4}'([a-z_]+)':/gm)].map((x) => x[1])
    expect(keys.sort()).toEqual([...SUBJECTS].sort())
  })
  it('the no-subject and reference lists name real verbs and types', () => {
    for (const v of NO_SUBJECT_VERBS) expect(VERBS).toContain(v)
    for (const s of REFERENCE_TYPES) expect(SUBJECTS).toContain(s)
  })
})

describe.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s', (_lang, msgs) => {
  it.each(VERBS)('verb %s has a sentence, with {subject} exactly when it is about somebody', (verb) => {
    const s = resolve(msgs, `${ACTIVITY_KEY}.verb.${verb}`)
    expect(typeof s).toBe('string')
    expect((s as string).includes('{subject}')).toBe(!NO_SUBJECT_VERBS.includes(verb))
  })

  it.each(SUBJECTS)('subject %s has its neutral words (hidden, removed)', (type) => {
    for (const state of ['hidden', 'removed']) {
      const w = resolve(msgs, `${ACTIVITY_KEY}.subject.${type}.${state}`)
      expect(typeof w).toBe('string')
      expect((w as string).length).toBeGreaterThan(0)
    }
    const named = resolve(msgs, `${ACTIVITY_KEY}.subject.${type}.named`)
    if (REFERENCE_TYPES.includes(type)) expect(named).toEqual(expect.stringContaining('{label}'))
    else expect(named).toBeUndefined()
  })

  it('no sentence leaves a placeholder the card does not fill', () => {
    const verbs = resolve(msgs, `${ACTIVITY_KEY}.verb`) as Record<string, string>
    for (const s of Object.values(verbs)) expect(s.replace('{subject}', '')).not.toMatch(/\{\w+\}/)
    expect(Object.keys(verbs).sort()).toEqual([...VERBS].sort())
  })
})
