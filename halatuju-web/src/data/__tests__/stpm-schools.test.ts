import { STPM_SCHOOLS, stpmSchoolsForStream } from '@/data/stpm-schools'

describe('STPM_SCHOOLS data', () => {
  it('loads all Form 6 centres', () => {
    expect(STPM_SCHOOLS.length).toBeGreaterThan(500)
  })

  it('uses only the two canonical stream labels', () => {
    const labels = new Set<string>()
    STPM_SCHOOLS.forEach((s) => s.streams.forEach((l) => labels.add(l)))
    expect([...labels].sort()).toEqual(['Sains', 'Sains Sosial'])
  })
})

describe('stpmSchoolsForStream', () => {
  it('returns only Sains-stream centres for "sains"', () => {
    const result = stpmSchoolsForStream('sains')
    expect(result.length).toBeGreaterThan(0)
    expect(result.every((s) => s.streams.includes('Sains'))).toBe(true)
  })

  it('returns only Sains Sosial-stream centres for "sains_sosial"', () => {
    const result = stpmSchoolsForStream('sains_sosial')
    expect(result.length).toBeGreaterThan(0)
    expect(result.every((s) => s.streams.includes('Sains Sosial'))).toBe(true)
  })

  it('returns every centre for "not_sure" (undecided students still pick a school)', () => {
    expect(stpmSchoolsForStream('not_sure').length).toBe(STPM_SCHOOLS.length)
  })

  it('returns every centre for an unknown key (defensive fallback)', () => {
    expect(stpmSchoolsForStream('totally-bogus').length).toBe(STPM_SCHOOLS.length)
  })

  it('Sains and Sains Sosial overlap on schools that offer both streams', () => {
    const sains = new Set(stpmSchoolsForStream('sains').map((s) => s.code))
    const social = new Set(stpmSchoolsForStream('sains_sosial').map((s) => s.code))
    const both = [...sains].filter((c) => social.has(c))
    expect(both.length).toBeGreaterThan(0)
  })
})
