import { gradedOnly } from './gradeEntry'

describe('gradedOnly', () => {
  it('keeps only the subjects that carry a grade', () => {
    expect(gradedOnly(['phy', 'chem', 'bio'], { phy: 'A', bio: 'B+' })).toEqual(['phy', 'bio'])
  })

  it('is stricter than filter(Boolean) — a named but ungraded slot is dropped', () => {
    // The #105 shape: 'bio' sat in the saved stream list with no grade behind it. `filter(Boolean)`
    // kept it, because the slot is not empty — it names a subject nobody sat.
    const slots = ['bio', 'addmath']
    const grades = { addmath: 'A-' }
    expect(slots.filter(Boolean)).toEqual(['bio', 'addmath'])
    expect(gradedOnly(slots, grades)).toEqual(['addmath'])
  })

  it('drops empty slots too', () => {
    expect(gradedOnly(['', 'poa', ''], { poa: 'A' })).toEqual(['poa'])
  })

  it('treats a blank grade string as no grade', () => {
    expect(gradedOnly(['poa'], { poa: '' })).toEqual([])
  })

  it('keeps the original order', () => {
    expect(gradedOnly(['ekonomi', 'poa', 'geo'], { geo: 'A', ekonomi: 'B', poa: 'C' }))
      .toEqual(['ekonomi', 'poa', 'geo'])
  })

  it('returns nothing when nothing is graded', () => {
    expect(gradedOnly(['phy', 'chem'], {})).toEqual([])
  })

  it('leaves duplicates alone rather than hiding them', () => {
    // The dropdowns exclude an already-picked subject, so a duplicate means a bug upstream.
    // Collapsing it here would make that bug invisible.
    expect(gradedOnly(['poa', 'poa'], { poa: 'A' })).toEqual(['poa', 'poa'])
  })
})
