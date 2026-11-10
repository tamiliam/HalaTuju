/**
 * Sprint M1a review (owner O18): `has_scholars` — the refusal of Remove from Mentors, Delete and Revoke
 * while the person still mentors anyone — is said in the reader's language, with the API's count.
 */
import { scholarsRefusal } from '../staffRefusals'

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
