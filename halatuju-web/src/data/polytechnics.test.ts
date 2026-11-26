import { POLYTECHNICS } from './polytechnics'

describe('POLYTECHNICS (TD-767)', () => {
  it('holds the 36 public polytechnics, no duplicates, no community colleges', () => {
    expect(POLYTECHNICS).toHaveLength(36)
    expect(new Set(POLYTECHNICS.map((p) => p.name)).size).toBe(36)
    expect(new Set(POLYTECHNICS.map((p) => p.hint)).size).toBe(36)
    for (const p of POLYTECHNICS) {
      expect(p.name.startsWith('Politeknik ')).toBe(true)
      expect(p.name).not.toMatch(/kolej komuniti/i)
    }
    expect(POLYTECHNICS.map((p) => p.name)).toContain('Politeknik Ungku Omar')
  })
})
