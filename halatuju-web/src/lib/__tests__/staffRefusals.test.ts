/**
 * Sprint M1a review (owner O18): `has_scholars` — the refusal of Remove from Mentors, Delete and Revoke
 * while the person still mentors anyone — is said in the reader's language, with the API's count.
 */
import { refusalOf, refusalWords, scholarsRefusal } from '../staffRefusals'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const t = (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k)
const refused = (code: string, body?: Record<string, unknown>) =>
  Object.assign(new Error('server text'), { status: 409, code, body })

describe('scholarsRefusal', () => {
  it('names the count the API sent, under the person page key by default', () => {
    expect(scholarsRefusal(refused('has_scholars', { scholars_now: 3 }), t))
      .toBe('admin.person.revokeHasScholars {"n":"3"}')
  })

  it('takes the caller\'s own key (the Mentors table)', () => {
    expect(scholarsRefusal(refused('has_scholars', { scholars_now: 1 }), t, 'admin.mentors.error.has_scholars'))
      .toBe('admin.mentors.error.has_scholars {"n":"1"}')
  })

  it('leaves every other error to the caller', () => {
    expect(scholarsRefusal(refused('last_org_admin'), t)).toBeNull()
    expect(scholarsRefusal(new Error('offline'), t)).toBeNull()
    expect(scholarsRefusal(null, t)).toBeNull()
  })
})

describe('M1b: refusalWords / refusalOf', () => {
  const t = (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k)

  it('words a plain code by its key', () => {
    expect(refusalWords('last_table', t)).toBe('admin.refusal.last_table')
    expect(refusalWords('sole_org_admin', t)).toBe('admin.refusal.sole_org_admin')
  })

  it('words a counted code as one, many, or some when no count came', () => {
    expect(refusalWords('has_open_cases', t, { open_cases: 1 })).toBe('admin.refusal.has_open_cases.one {"n":"1"}')
    expect(refusalWords('has_open_cases', t, { open_cases: 4 })).toBe('admin.refusal.has_open_cases.many {"n":"4"}')
    expect(refusalWords('run_in_progress', t, { runs_in_progress: 2 })).toBe('admin.refusal.run_in_progress.many {"n":"2"}')
    expect(refusalWords('has_scholars', t)).toBe('admin.refusal.has_scholars.some')
  })

  it('gives null for an unknown or missing code, so the caller keeps the server\'s sentence', () => {
    expect(refusalWords('something_new', t)).toBeNull()
    expect(refusalWords(null, t)).toBeNull()
  })

  it('reads a thrown 409\'s code and body', () => {
    const err = Object.assign(new Error('x'), { code: 'has_scholars', body: { scholars_now: 3 } })
    expect(refusalOf(err, t)).toBe('admin.refusal.has_scholars.many {"n":"3"}')
    expect(refusalOf(new Error('plain'), t)).toBeNull()
  })

  it('every refusal key exists in en, ms and ta', () => {
    for (const msgs of [en, ms, ta]) {
      const r = (msgs as { admin: { refusal: Record<string, unknown> } }).admin.refusal
      for (const c of ['last_table', 'mentors_only', 'lead_fixed', 'qc_sees_all', 'not_arrived', 'self',
        'last_org_admin', 'sole_org_admin', 'has_unfinished_work', 'staff_mentor']) expect(typeof r[c]).toBe('string')
      for (const c of ['has_open_cases', 'run_in_progress', 'has_scholars']) {
        const v = r[c] as Record<string, string>
        for (const f of ['one', 'many', 'some']) expect(typeof v[f]).toBe('string')
      }
    }
  })
})
