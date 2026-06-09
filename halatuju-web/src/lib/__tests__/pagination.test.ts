import { pageWindow } from '@/lib/pagination'

describe('pageWindow', () => {
  it('shows every page when the total is small', () => {
    expect(pageWindow(1, 1)).toEqual([1])
    expect(pageWindow(2, 3)).toEqual([1, 2, 3])
  })

  it('puts a gap on the right when near the start', () => {
    expect(pageWindow(1, 10)).toEqual([1, 2, 'gap', 10])
  })

  it('puts a gap on the left when near the end', () => {
    expect(pageWindow(10, 10)).toEqual([1, 'gap', 9, 10])
  })

  it('puts gaps on both sides in the middle', () => {
    expect(pageWindow(5, 10)).toEqual([1, 'gap', 4, 5, 6, 'gap', 10])
  })

  it('never emits a gap that hides only a single page', () => {
    // page 2 of 4: 1,2,3 then 4 — the 3→4 step is contiguous, no gap.
    expect(pageWindow(2, 4)).toEqual([1, 2, 3, 4])
  })

  it('keeps the window compact for very large totals (no 67-button blowup)', () => {
    const out = pageWindow(34, 68)
    expect(out).toEqual([1, 'gap', 33, 34, 35, 'gap', 68])
    expect(out.length).toBeLessThanOrEqual(7)
  })

  it('dedupes when current sits next to the edges', () => {
    expect(pageWindow(2, 10)).toEqual([1, 2, 3, 'gap', 10])
    expect(pageWindow(9, 10)).toEqual([1, 'gap', 8, 9, 10])
  })
})
