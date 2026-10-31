/**
 * Same-name schools carry their town (owner, 2026-10-31). A name used by more than one school in the
 * national secondary list is stored as "<NAME>, <TOWN>" ("SMK CONVENT, TAIPING"), in BOTH lists, so
 * the name a student picks says which school it is. Every other name is untouched. The lists are
 * written by `halatuju_api/scripts/school_town_names.py`; the server's copy of the set is checked
 * against these files by `test_same_name_schools.py`.
 */
import { SECONDARY_SCHOOLS, searchSchools } from '@/data/secondary-schools'
import { STPM_SCHOOLS } from '@/data/stpm-schools'

// Names are compared as a reader compares them: case, punctuation and spacing ignored, so
// "SMK ST. ANTHONY" and "SMK ST ANTHONY" are ONE name (review 2, 2026-10-31).
const norm = (n: string) => n.toUpperCase().replace(/'/g, '').replace(/[^A-Z0-9]+/g, ' ').trim()
const dupes = (names: string[]) => {
  const seen = new Set<string>()
  return names.map(norm).filter((n) => (seen.has(n) ? true : (seen.add(n), false)))
}
// The one MOE name that holds a comma of its own; nothing shares it.
const OWN_COMMA = 'SMK PETAGAS, PENAMPANG'
const withTown = (names: string[]) => names.filter((n) => n.includes(', ') && n !== OWN_COMMA)

describe('no two schools share a name, even by punctuation', () => {
  it('in the secondary list', () => {
    expect(dupes(SECONDARY_SCHOOLS.map((s) => s.name))).toEqual([])
  })
  it('in the Form 6 list', () => {
    expect(dupes(STPM_SCHOOLS.map((s) => s.name))).toEqual([])
  })
})

describe('only the shared names changed', () => {
  it('184 secondary rows and 53 Form 6 rows carry a town; the rest are as the MOE wrote them', () => {
    expect(withTown(SECONDARY_SCHOOLS.map((s) => s.name))).toHaveLength(184)
    expect(withTown(STPM_SCHOOLS.map((s) => s.name))).toHaveLength(53)
  })
  it('names that differ only by punctuation carry their towns too', () => {
    const names = SECONDARY_SCHOOLS.map((s) => s.name)
    expect(names).toContain('SMK ST. ANTHONY, TELUK INTAN')
    expect(names).toContain('SMK METHODIST ACS, SEREMBAN')
  })
  it('a name nobody else uses is unchanged', () => {
    const codes = (name: string) => SECONDARY_SCHOOLS.filter((s) => s.name === name).map((s) => s.code)
    expect(codes('SMK (P) TEMENGGONG IBRAHIM')).toEqual(['JEB0016'])
    expect(STPM_SCHOOLS.find((s) => s.code === 'JEB0016')?.name).toBe('SMK (P) TEMENGGONG IBRAHIM')
    expect(STPM_SCHOOLS.some((s) => s.name === 'KTE PONTIAN')).toBe(true)
    expect(SECONDARY_SCHOOLS.some((s) => s.name === OWN_COMMA)).toBe(true)
  })
  it('every town-carrying name is a name another school uses too', () => {
    const bare = new Map<string, number>()
    for (const n of SECONDARY_SCHOOLS.map((s) => s.name)) {
      const b = withTown([n]).length ? n.slice(0, n.lastIndexOf(', ')) : n
      bare.set(norm(b), (bare.get(norm(b)) ?? 0) + 1)
    }
    for (const n of withTown(SECONDARY_SCHOOLS.map((s) => s.name))) {
      expect([n, bare.get(norm(n.slice(0, n.lastIndexOf(', '))))! > 1]).toEqual([n, true])
    }
  })
  it('the examples: SMK CONVENT in Taiping, SMK CHUNG HUA in Miri and Sibu', () => {
    expect(SECONDARY_SCHOOLS.some((s) => s.name === 'SMK CONVENT, TAIPING')).toBe(true)
    expect(STPM_SCHOOLS.map((s) => s.name).filter((n) => n.startsWith('SMK CHUNG HUA')).sort())
      .toEqual(['SMK CHUNG HUA, MIRI', 'SMK CHUNG HUA, SIBU'])
  })
  it('the town is searchable: "convent taiping" finds it', () => {
    expect(searchSchools('convent taiping').map((s) => s.name)).toContain('SMK CONVENT, TAIPING')
  })
})
