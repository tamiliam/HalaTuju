/**
 * drift-test: the `doc_seen` codes and `final_owed` the genuineness note keys on are the backend's own
 * (`genuineness/matric_poly_doc.py`, `genuineness/bands.py`). The note's behaviour is
 * `GenuinenessNote.test.tsx`.
 */
import { readApi } from '@/test/apiSource'

describe('GenuinenessNote — the backend codes it keys on', () => {
  test('the codes are the backend\'s own', () => {
    const src = readApi('apps/scholarship/genuineness/matric_poly_doc.py')
    for (const code of ['matric_result_slip', 'poly_result_slip', 'poly_portal_page', 'matric_offer_letter',
      'matric_transcript_not_final', 'poly_transcript_not_final']) {
      expect(src).toContain(`'${code}'`)
    }
    expect(readApi('apps/scholarship/genuineness/bands.py')).toContain("FINAL_OWED = 'final_owed'")
  })
})
