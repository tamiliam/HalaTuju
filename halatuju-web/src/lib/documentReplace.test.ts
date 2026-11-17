import { isSettledDoc, replacesLeft } from '@/lib/documentReplace'
import type { ApplicantDocument } from '@/lib/api'

const doc = (over: Record<string, unknown> = {}) =>
  ({ id: 1, doc_type: 'ic', replace_count: 0, replace_limit: 3, ...over }) as unknown as ApplicantDocument

describe('isSettledDoc (the replace hint) and replacesLeft', () => {
  it('a copy that read fine is settled', () => {
    expect(isSettledDoc(doc({ authenticity: { status: 'genuine' } }))).toBe(true)
    expect(isSettledDoc(doc({ vision_fields: { student_verdict: 'review_manually' } }))).toBe(true)
  })
  it('a suspect copy the student is shown (serializer sends authenticity) needs a fix', () => {
    expect(isSettledDoc(doc({ authenticity: { status: 'suspect' } }))).toBe(false)
  })
  it('a suspect the serializer hides (authenticity null, e.g. salary slip) reads as settled', () => {
    expect(isSettledDoc(doc({ doc_type: 'salary_slip', authenticity: null }))).toBe(true)
  })
  it('a wrong-type or problem-verdict copy needs a fix', () => {
    expect(isSettledDoc(doc({ authenticity: { status: 'not_ic' } }))).toBe(false)
    expect(isSettledDoc(doc({ vision_fields: { student_verdict: 'wrong_doc' } }))).toBe(false)
  })
  it('a copy the reviewer returned (rejected) needs a fix', () => {
    expect(isSettledDoc(doc({ verification_status: 'rejected', replace_count: 3 }))).toBe(false)
    expect(isSettledDoc(doc({ verification_status: 'accepted' }))).toBe(true)
  })
  it('replacesLeft never goes below zero', () => {
    expect(replacesLeft(doc({ replace_count: 5 }))).toBe(0)
  })
  it("replacesLeft is the server's own number when served (removed history and a person's ask included)", () => {
    expect(replacesLeft(doc({ replace_count: 0, replaces_left: 1 }))).toBe(1)
    expect(replacesLeft(doc({ replace_count: 3, replaces_left: 1 }))).toBe(1)
    expect(replacesLeft(doc({ replace_count: 1, replaces_left: 0 }))).toBe(0)
  })
})
