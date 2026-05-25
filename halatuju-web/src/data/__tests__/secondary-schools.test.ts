import { SECONDARY_SCHOOLS, searchSchools } from '@/data/secondary-schools'

describe('SECONDARY_SCHOOLS data', () => {
  it('loads the full MOE secondary-school list', () => {
    expect(SECONDARY_SCHOOLS.length).toBe(2480)
  })
  it('every entry has a name and state', () => {
    expect(SECONDARY_SCHOOLS.every((s) => s.name && s.state)).toBe(true)
  })
})

describe('searchSchools', () => {
  it('returns nothing for queries under 2 characters', () => {
    expect(searchSchools('')).toEqual([])
    expect(searchSchools('s')).toEqual([])
  })
  it('finds schools by a case-insensitive substring of the name', () => {
    const res = searchSchools('smk')
    expect(res.length).toBeGreaterThan(0)
    expect(res.every((s) => s.name.toLowerCase().includes('smk'))).toBe(true)
  })
  it('caps results at the limit', () => {
    expect(searchSchools('sekolah', 5).length).toBeLessThanOrEqual(5)
    expect(searchSchools('a', 5)).toEqual([]) // still under 2 chars
  })
  it('ranks prefix matches ahead of mid-string matches', () => {
    // A real school name to anchor on; pick the first one and search its prefix.
    const sample = SECONDARY_SCHOOLS.find((s) => s.name.length > 6)!
    const prefix = sample.name.slice(0, 5).toLowerCase()
    const res = searchSchools(prefix, 8)
    // The top hit must itself start with the query (prefix matches come first).
    expect(res[0].name.toLowerCase().startsWith(prefix)).toBe(true)
  })
})
