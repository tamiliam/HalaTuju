/**
 * Officer income vocabulary — the ABSENCE guard.
 *
 * ⚠ B40 IS MALAYSIA'S NATIONAL INCOME BAND, NOT A PROPERTY OF ANY GIFT. A gift may set no
 * income ceiling at all (measured on production 2026-09-09: the `test` round has both
 * `income_ceiling` and `per_capita_ceiling` NULL), and the officer verdict card still said
 * "Income (B40)" and reasoned about "the B40 line". The same fault ran the other way in
 * `utility_percapita_high`, which named M40/T20.
 *
 * ⚠ THIS GUARD WALKS EVERY LEAF IN THE OFFICER TREES, NOT THE TWELVE STRINGS THAT WERE FIXED.
 * A guard written from the instance you just fixed is scoped to that instance (lessons.md,
 * 2026-09-08) — and `utility_percapita_high` is the proof: it was NOT in the owner-approved
 * list of eleven and carried the identical fault.
 *
 * ⚠ VERIFY A RENAME BY ABSENCE. "is the new wording present?" passes while the retired
 * sentence sits beside it (lessons.md, 2026-09-08). Hence the retired-sentence block below.
 *
 * IN SCOPE: the officer's own surfaces only — the verdict card, the interview agenda, the
 * anomaly flags. The STUDENT- and SPONSOR-facing pages legitimately say B40 today (the apply
 * page, the landing page, the sign-in prompt, the sponsor cards); those are logged as separate,
 * already-planned work and MUST NOT be swept in here.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

/** The DOSM income bands. None of them describes a gift. */
const BANDS = ['B40', 'M40', 'T20'] as const

/** Officer-facing message subtrees. */
const OFFICER_PREFIXES = [
  'admin.scholarship.verdict.',
  'admin.scholarship.agenda.',
  'admin.scholarship.anomaly.',
] as const

/**
 * Sentences that were RETIRED on 2026-09-10. A presence check on the new wording cannot see
 * these; only asking whether they are GONE can. Listed by the words a reader would recognise,
 * not by key, because the failure mode is the sentence reappearing SOMEWHERE ELSE.
 */
const RETIRED = [
  'Income (B40)',
  'B40 status confirmed',
  'the B40 line',
  "household's B40 need",
  'salary documents for B40',
  'consistent with a B40 household',
  'M40/T20 consumption pattern',
  'unusual for a B40 student',
] as const

function flatten(obj: unknown, prefix = '', out: Record<string, string> = {}): Record<string, string> {
  if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      flatten(v, prefix ? `${prefix}.${k}` : k, out)
    }
  } else if (typeof obj === 'string') {
    out[prefix] = obj
  }
  return out
}

const LOCALES: Record<string, unknown> = { en, ms, ta }

function officerLeaves(msgs: unknown): Array<[string, string]> {
  return Object.entries(flatten(msgs))
    .filter(([p]) => OFFICER_PREFIXES.some((pre) => p.startsWith(pre)))
}

describe('officer income vocabulary', () => {
  it('scans a real corpus (a broken scanner must fail, not silently pass)', () => {
    for (const [loc, msgs] of Object.entries(LOCALES)) {
      // ~100 verdict items + agenda + anomaly leaves per locale. A wrong prefix reads 0.
      expect(officerLeaves(msgs).length).toBeGreaterThan(80)
    }
    expect(Object.keys(LOCALES)).toHaveLength(3)
  })

  it('names no DOSM income band anywhere in the officer trees', () => {
    const hits: string[] = []
    for (const [loc, msgs] of Object.entries(LOCALES)) {
      for (const [p, v] of officerLeaves(msgs)) {
        for (const band of BANDS) {
          if (v.includes(band)) hits.push(`${loc}:${p} — "${band}" in "${v.slice(0, 70)}"`)
        }
      }
    }
    expect(hits).toEqual([])
  })

  it('carries none of the retired sentences, in any locale or any key', () => {
    // Whole-file, not the officer trees: a retired sentence coming back on ANOTHER page is
    // the failure this is written for.
    const hits: string[] = []
    for (const [loc, msgs] of Object.entries(LOCALES)) {
      for (const [p, v] of Object.entries(flatten(msgs))) {
        for (const s of RETIRED) {
          if (v.includes(s)) hits.push(`${loc}:${p} — "${s}"`)
        }
      }
    }
    expect(hits).toEqual([])
  })

  it('has the no-means-test sentence in all three languages', () => {
    for (const [loc, msgs] of Object.entries(LOCALES)) {
      const flat = flatten(msgs)
      const key = 'admin.scholarship.verdict.item.income_not_means_tested'
      expect(`${loc}: ${flat[key] ?? 'MISSING'}`).not.toContain('MISSING')
      expect((flat[key] || '').length).toBeGreaterThan(30)
    }
  })

  it('leaves the student- and sponsor-facing B40 copy alone (out of scope, still planned)', () => {
    // ⚠ NOT an aspiration — a fence. Sweeping these in here would change what applicants and
    // sponsors are told, which is a different sprint with a different owner check.
    const flat = flatten(en)
    expect(flat['scholarship.apply.title']).toContain('B40')
    expect(flat['scholarship.landing.req.item2']).toContain('B40')
  })
})
