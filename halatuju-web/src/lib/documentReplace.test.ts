import { isSettledDoc, replacesLeft } from '@/lib/documentReplace'
import type { ApplicantDocument } from '@/lib/api'

const doc = (over: Record<string, unknown> = {}) =>
  ({ id: 1, doc_type: 'ic', replace_count: 0, replace_limit: 3, ...over }) as unknown as ApplicantDocument

describe('isSettledDoc agrees with the server rule', () => {
  it('a copy that read fine is settled: the counter shows', () => {
    expect(isSettledDoc(doc({ authenticity: { status: 'genuine' } }))).toBe(true)
    expect(isSettledDoc(doc({ vision_fields: { student_verdict: 'review_manually' } }))).toBe(true)
  })
  it('a suspect copy the student is shown (serializer sends authenticity) needs a fix: no counter, no cap', () => {
    expect(isSettledDoc(doc({ authenticity: { status: 'suspect' } }))).toBe(false)
  })
  it('a suspect the serializer hides (authenticity null, e.g. salary slip) is counted like the server', () => {
    expect(isSettledDoc(doc({ doc_type: 'salary_slip', authenticity: null }))).toBe(true)
  })
  it('a wrong-type or problem-verdict copy needs a fix', () => {
    expect(isSettledDoc(doc({ authenticity: { status: 'not_ic' } }))).toBe(false)
    expect(isSettledDoc(doc({ vision_fields: { student_verdict: 'wrong_doc' } }))).toBe(false)
  })
  it('replacesLeft never goes below zero', () => {
    expect(replacesLeft(doc({ replace_count: 5 }))).toBe(0)
  })
})
