/**
 * Document card file layout — and the guard against the bug that produced it (2026-07-26).
 *
 * The "tidier document rows" change (2026-07-24) gave every document card a bordered chip with
 * Replace + Remove grouped inside it — EXCEPT `str` / `salary_slip` / `epf`, which it exempted as
 * "multi-file". That exemption mirrored `DocumentListCreateView.MULTI_INSTANCE_DOC_TYPES`, a
 * backend rule already retired on 2026-06-05 (every doc type is single-instance; an upload
 * replaces its `(doc_type, household_member)` slot). So the mother's STR and salary-slip cards
 * alone kept Replace up in the header, away from a bare unbordered filename.
 *
 * ⚠ THIS FILE IS NOW THE PURE RULE ONLY. It used to carry a second half that read
 * `ScholarshipDocuments.tsx` as TEXT, looking for a re-introduced `MULTI_INSTANCE` constant —
 * which could only ever catch the exemption coming back under the same NAME, and said nothing
 * about where Replace actually sits on screen. That half was replaced in code health H6 by
 * rendered assertions in `src/components/ScholarshipDocuments.test.tsx`
 * ("no income-proof document gets its own layout"), which mount the component and check the
 * chip for STR, the salary slip and the EPF statement against a control type.
 */
import { docFileLayout, DOC_TYPES } from '@/lib/scholarship'

describe('docFileLayout', () => {
  it('shows nothing when the card holds no file', () => {
    expect(docFileLayout(0)).toBe('none')
  })

  it('gives ONE file the inline chip (Replace beside the file, not in the header)', () => {
    expect(docFileLayout(1)).toBe('chip')
  })

  it('falls back to the list when a card holds more than one file', () => {
    // Reachable during the TD-115 slot backfill: an STR earner's card also shows the legacy
    // untagged copy beside the member-tagged one.
    expect(docFileLayout(2)).toBe('list')
    expect(docFileLayout(5)).toBe('list')
  })

  it('treats a negative count as empty rather than throwing', () => {
    expect(docFileLayout(-1)).toBe('none')
  })

  it('exempts no doc type — income proofs get the chip like everything else', () => {
    // The regression: `str` / `salary_slip` / `epf` were special-cased. The rule takes only a
    // count now, so there is nowhere for a doc type to be exempted; assert the income types are
    // still real doc types so this test cannot pass vacuously after a rename.
    for (const dt of ['str', 'salary_slip', 'epf']) {
      expect(DOC_TYPES as readonly string[]).toContain(dt)
    }
    expect(docFileLayout(1)).toBe('chip')
  })
})
