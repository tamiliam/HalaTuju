/**
 * Third results route S3a/S3b: this browser's results copy follows the server's two rules — one
 * higher qualification at a time, and "SPM results only" (`lib/resultsLocal.ts`).
 */
import { clearHigherResultsLocally, keepOneHigherLocally } from '@/lib/resultsLocal'
import {
  KEY_EXAM_TYPE, KEY_GRADES, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO,
  KEY_RESULTS_EXAM_TYPE, KEY_SPM_PREREQ, KEY_STPM_CGPA, KEY_STPM_GRADES,
} from '@/lib/storage'

function store(init: Record<string, string> = {}) {
  const m = new Map(Object.entries(init))
  return {
    getItem: (k: string) => (m.has(k) ? (m.get(k) as string) : null),
    setItem: (k: string, v: string) => { m.set(k, v) },
    removeItem: (k: string) => { m.delete(k) },
    m,
  }
}

describe('keepOneHigherLocally', () => {
  it('completing the STPM form drops the third route', () => {
    const s = store({ [KEY_HIGHER_CGPA]: '3.2', [KEY_HIGHER_KOKO]: '8', [KEY_HIGHER_INSTITUTION]: 'public',
                      [KEY_STPM_CGPA]: '3.7' })
    keepOneHigherLocally('stpm', s)
    expect([...s.m.keys()]).toEqual([KEY_STPM_CGPA])
  })

  it('completing the third-route form drops the STPM entries', () => {
    const s = store({ [KEY_STPM_GRADES]: '{}', [KEY_STPM_CGPA]: '3.7', [KEY_HIGHER_CGPA]: '3.2' })
    keepOneHigherLocally('third', s)
    expect([...s.m.keys()]).toEqual([KEY_HIGHER_CGPA])
  })
})

describe('clearHigherResultsLocally', () => {
  it('removes every higher result, keeps SPM, records SPM as the results held', () => {
    const s = store({ [KEY_STPM_CGPA]: '3.7', [KEY_HIGHER_CGPA]: '3.1', [KEY_GRADES]: '{"bm":"A"}',
                      [KEY_RESULTS_EXAM_TYPE]: 'stpm', [KEY_EXAM_TYPE]: 'stpm' })
    clearHigherResultsLocally(s)
    expect(s.getItem(KEY_STPM_CGPA)).toBeNull()
    expect(s.getItem(KEY_HIGHER_CGPA)).toBeNull()
    expect(s.getItem(KEY_GRADES)).toBe('{"bm":"A"}')
    expect([s.getItem(KEY_RESULTS_EXAM_TYPE), s.getItem(KEY_EXAM_TYPE)]).toEqual(['spm', 'spm'])
  })

  it('the STPM page\'s SPM block becomes the SPM record when the SPM form was never filled here', () => {
    const s = store({ [KEY_SPM_PREREQ]: '{"bm":"B"}', [KEY_STPM_CGPA]: '3.7' })
    clearHigherResultsLocally(s)
    expect(s.getItem(KEY_GRADES)).toBe('{"bm":"B"}')
    expect(s.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('spm')
  })

  it('with no SPM grades at all, no completion is claimed', () => {
    const s = store({ [KEY_STPM_CGPA]: '3.7', [KEY_RESULTS_EXAM_TYPE]: 'stpm' })
    clearHigherResultsLocally(s)
    expect(s.getItem(KEY_RESULTS_EXAM_TYPE)).toBeNull()
  })
})
