import { levelOf, filterPool, poolFacets } from './sponsorFilter'

const rows = [
  { field: 'Civil Engineering', state: 'Negeri Sembilan', academic: 'SPM · 5A 3B' },
  { field: 'Computer Science', state: 'W.P. Kuala Lumpur', academic: 'SPM · 6A 2B' },
  { field: 'Education', state: 'Kedah', academic: 'STPM · PNGK 3.0' },
  { field: 'Accountancy', state: 'Sabah', academic: 'SPM · 7A 1B' },
]

describe('levelOf', () => {
  it('reads SPM and STPM from the band', () => {
    expect(levelOf('SPM · 7A 1B')).toBe('SPM')
    expect(levelOf('STPM · PNGK 3.0')).toBe('STPM')
  })
  it('reads the third results route by its plain name (S2b, superseding "Diploma is unknown")', () => {
    expect(levelOf('Matriculation · CGPA 3.47')).toBe('Matriculation')
    expect(levelOf('Asasi')).toBe('Asasi')                 // no usable CGPA: the bare name
    expect(levelOf('Diploma · CGPA 2.80')).toBe('Diploma')
  })
  it('returns empty for an unknown band', () => {
    expect(levelOf('')).toBe('')
    expect(levelOf('PhD · 3.5')).toBe('')
    expect(levelOf('Diplomacy · 3.5')).toBe('')            // a name, not a prefix
  })
})

describe('filterPool', () => {
  it('returns everything when no filter is set', () => {
    expect(filterPool(rows, {})).toHaveLength(4)
  })
  it('filters by field, state and level independently', () => {
    expect(filterPool(rows, { field: 'Education' })).toHaveLength(1)
    expect(filterPool(rows, { state: 'Sabah' })).toHaveLength(1)
    expect(filterPool(rows, { level: 'SPM' })).toHaveLength(3)
    expect(filterPool(rows, { level: 'STPM' })).toHaveLength(1)
  })
  it('combines filters (AND)', () => {
    expect(filterPool(rows, { level: 'SPM', state: 'Sabah' })).toHaveLength(1)
    expect(filterPool(rows, { level: 'STPM', state: 'Sabah' })).toHaveLength(0)
  })
})

describe('poolFacets', () => {
  it('returns distinct sorted facets', () => {
    const f = poolFacets(rows)
    expect(f.fields).toEqual(['Accountancy', 'Civil Engineering', 'Computer Science', 'Education'])
    expect(f.states).toContain('Sabah')
    expect(f.levels).toEqual(['SPM', 'STPM'])
  })
  it('drops empty levels', () => {
    // 'Diploma' was the unknown example here until S2b made it a level; an unknown band stays out.
    expect(poolFacets([{ field: 'X', state: 'Y', academic: 'Certificate' }]).levels).toEqual([])
  })
})
