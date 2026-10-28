/**
 * THE DRIFT TEST for the STPM subject list — `STPM_SUBJECTS` (`lib/subjects.ts`, named by its
 * `drift-test:` marker) against the server's `STPM_SUBJECT_KEYS`
 * (`halatuju_api/apps/courses/stpm_subjects.py`). STPM CGPA sprint C1, 2026-10-28.
 *
 * ⚠ THE HARM RUNS BOTH WAYS. A subject the server knows and the form lacks cannot be entered —
 * case #184 took Sains Sukan and could enter only three subjects, so no PNGK could be worked out.
 * A key the form offers and the server does not know is a grade the slip check, the reports and
 * the course requirements never read.
 */
import { STPM_SUBJECTS, STPM_SUBJECT_TO_API_KEY, stpmSubjectLabel } from '@/lib/subjects'
import { pySeq, readApi } from '@/test/apiSource'

const apiKeys = pySeq(readApi('apps/courses/stpm_subjects.py'), 'STPM_SUBJECT_KEYS')

describe('parse sanity — the server list was really found', () => {
  test('at least the 23 MPM subjects, Pengajian Am first, Sains Sukan among them', () => {
    expect(apiKeys.length).toBeGreaterThanOrEqual(23)
    expect(apiKeys[0]).toBe('PA')
    expect(apiKeys).toEqual(expect.arrayContaining(['SAINS_SUKAN', 'BAHASA_ARAB', 'TAHFIZ_AL_QURAN']))
  })
})

describe('the form offers exactly the server keys', () => {
  test('same keys, same order', () => {
    expect(STPM_SUBJECTS.map((s) => s.id)).toEqual(apiKeys)
  })

  test('every subject but Pengajian Am has a quiz key, and no quiz key is orphaned', () => {
    const ids = STPM_SUBJECTS.map((s) => s.id)
    expect(ids.filter((id) => !STPM_SUBJECT_TO_API_KEY[id])).toEqual([])
    expect(Object.keys(STPM_SUBJECT_TO_API_KEY).filter((k) => !ids.includes(k))).toEqual([])
  })

  test('Sains Sukan can be chosen in either stream, so #184 can enter four subjects', () => {
    expect(STPM_SUBJECTS.find((s) => s.id === 'SAINS_SUKAN')?.stream).toBe('both')
  })
})

describe('labels', () => {
  test('every subject is named in all three languages', () => {
    const blank = STPM_SUBJECTS.filter((s) => !s.name.trim() || !s.en.trim() || !s.ta.trim())
    expect(blank.map((s) => s.id)).toEqual([])
  })

  test('the label follows the language; Malay is the certificate name', () => {
    const fizik = STPM_SUBJECTS.find((s) => s.id === 'PHYSICS')!
    expect(stpmSubjectLabel(fizik, 'en')).toBe('Physics')
    expect(stpmSubjectLabel(fizik, 'ms')).toBe('Fizik')
    expect(stpmSubjectLabel(fizik, 'ta')).toBe('இயற்பியல்')
  })
})
