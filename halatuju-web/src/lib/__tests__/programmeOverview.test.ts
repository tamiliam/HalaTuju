/**
 * The arithmetic behind the Programme Overview's charts (node — no DOM, by design).
 *
 * ⚠ THE GEOMETRY IS TESTED HERE RATHER THAN THROUGH A RENDERED SVG, because the half of a chart
 * that can be silently wrong is the half made of numbers: a bar that is 3px too short still looks
 * like a bar, and a donut whose arcs do not sum to the ring still looks like a donut. What the
 * component test next door proves is that the tokens and the labels reached the markup.
 */
import {
  FULL_BOX, SMALL_BOX, WIDE_BOX, bandTone, barLayout, donutArcs, has, lineLayout, monthLabel,
  num, rm, sliceClasses, weekLabel,
} from '@/lib/programmeOverview'

describe('rm — the money formatter, lifted from the sponsor card', () => {
  it('groups thousands and keeps both cents', () => {
    expect(rm('10650.22')).toBe('10,650.22')
    expect(rm('396000.00')).toBe('396,000.00')
    expect(rm('0.00')).toBe('0.00')
  })

  it('never invents cents it was not given, and never rounds', () => {
    // ⚠ The point of a money STRING: what the server computed is what the screen prints.
    expect(rm('1500')).toBe('1,500.00')
    expect(rm('27.51')).toBe('27.51')
  })
})

describe('num — parsed for geometry only', () => {
  it('reads a money string', () => {
    expect(num('27.51')).toBeCloseTo(27.51)
  })

  it('treats nonsense and blank as zero rather than NaN — a NaN bar has no height at all', () => {
    expect(num('')).toBe(0)
    expect(num('not a number')).toBe(0)
  })
})

describe('barLayout', () => {
  it('scales to the tallest bar across EVERY series — one unit, one scale', () => {
    const { bars, baseline } = barLayout([[1, 2], [4, 0]], WIDE_BOX)
    const plot = WIDE_BOX.height - WIDE_BOX.bottom - WIDE_BOX.top
    expect(baseline).toBe(WIDE_BOX.height - WIDE_BOX.bottom)
    expect(bars[1][0].height).toBeCloseTo(plot)          // the max
    expect(bars[0][1].height).toBeCloseTo(plot / 2)      // half of it, in the OTHER series
    expect(bars[1][1].height).toBe(0)
  })

  it('sits every bar ON the baseline', () => {
    const { bars, baseline } = barLayout([[3, 1]], WIDE_BOX)
    for (const bar of bars[0]) expect(bar.y + bar.height).toBeCloseTo(baseline)
  })

  it('draws NOTHING when everything is zero — a full bar for a zero would be a lie', () => {
    const { bars, max } = barLayout([[0, 0, 0]], WIDE_BOX)
    expect(max).toBe(0)
    expect(bars[0].map((b) => b.height)).toEqual([0, 0, 0])
  })

  it('keeps two series inside one column instead of overlapping them', () => {
    const { bars } = barLayout([[1, 1], [1, 1]], FULL_BOX)
    expect(bars[1][0].x).toBeGreaterThanOrEqual(bars[0][0].x + bars[0][0].width)
    // …and the whole column stays inside the box.
    const last = bars[1][1]
    expect(last.x + last.width).toBeLessThanOrEqual(FULL_BOX.width)
  })

  it('survives an empty series without dividing by zero', () => {
    const { bars, max } = barLayout([[]], WIDE_BOX)
    expect(bars[0]).toEqual([])
    expect(max).toBe(0)
  })
})

describe('lineLayout', () => {
  it('spreads the points across the box, one per column', () => {
    const { points } = lineLayout([1, 2, 3], WIDE_BOX)
    expect(points.length).toBe(3)
    expect(points[0].x).toBeLessThan(points[1].x)
    expect(points[2].x).toBeLessThan(WIDE_BOX.width)
  })

  /* ⚠⚠ THE NEGATIVE GAP IS THE CASE THIS FUNCTION EXISTS FOR. `released_cum − spent_cum` goes
   * below zero when somebody else tops a student's wallet up, which is allowed — and it is the
   * month an officer should ask about. Clamping it at zero would hide exactly that. */
  it('supports a negative value and puts the zero line ABOVE it', () => {
    const { points, zeroY, min } = lineLayout([100, 0, -50], SMALL_BOX)
    expect(min).toBe(-50)
    expect(zeroY).toBeLessThan(points[2].y)      // in SVG, larger y is lower down
    expect(points[0].y).toBeLessThan(zeroY)      // the positive month is above zero
  })

  it('keeps zero in the domain even when nothing is negative', () => {
    const { min, zeroY } = lineLayout([10, 20], SMALL_BOX)
    expect(min).toBe(0)
    expect(zeroY).toBe(SMALL_BOX.height - SMALL_BOX.bottom)
  })

  it('rests a flat series on the baseline rather than inventing a movement', () => {
    const { points } = lineLayout([0, 0, 0], WIDE_BOX)
    for (const p of points) expect(p.y).toBe(WIDE_BOX.height - WIDE_BOX.bottom)
  })
})

describe('donutArcs', () => {
  const rows = [
    { code: 'food', total: '75.00' },
    { code: 'groceries', total: '25.00' },
    { code: 'health', total: '0.00' },
    { code: 'none', total: '0.00' },
  ]

  it('gives each slice its share of the ring, in order', () => {
    const arcs = donutArcs(rows)
    const circumference = arcs[0].dash + arcs[0].gap
    expect(arcs[0].dash / circumference).toBeCloseTo(0.75)
    expect(arcs[1].dash / circumference).toBeCloseTo(0.25)
    expect(arcs[1].offset).toBeCloseTo(arcs[0].dash)
  })

  /* ⚠ A ZERO SLICE IS SKIPPED IN THE RING AND KEPT IN THE LEGEND — asserted from both sides,
   * because dropping it from the ring is correct and dropping it from the list is the bug. */
  it('skips a zero slice, so it cannot consume a colour', () => {
    const arcs = donutArcs(rows)
    expect(arcs.map((a) => a.code)).toEqual(['food', 'groceries'])
    expect(arcs.map((a) => a.rank)).toEqual([0, 1])
  })

  it('draws nothing at all when no category has any money', () => {
    expect(donutArcs([{ code: 'food', total: '0.00' }, { code: 'none', total: '0.00' }]))
      .toEqual([])
  })
})

describe('sliceClasses', () => {
  it('colours a ranked category from the eight swatches', () => {
    expect(sliceClasses('food', 0).stroke).toBe('stroke-category-1-dot')
    expect(sliceClasses('groceries', 1).dot).toBe('bg-category-2-dot')
  })

  it('wraps at eight, because eight swatches exist and nine categories can carry money', () => {
    expect(sliceClasses('transfer', 8).stroke).toBe('stroke-category-1-dot')
    expect(sliceClasses('transfer', 9).stroke).toBe('stroke-category-2-dot')
  })

  /* ⚠ THE TWO "WE DO NOT KNOW" STATES RECEDE, and neither ever takes a TONE: a tone says
   * something about a state, and an unsorted purchase is a gap in our own filing, not a problem
   * with the student. */
  it('puts the unknown states on ground tokens, never on a swatch and never on a tone', () => {
    expect(sliceClasses('none', 0)).toEqual({ stroke: 'stroke-ground-200', dot: 'bg-ground-200' })
    expect(sliceClasses('unsorted', 0)).toEqual({ stroke: 'stroke-ground-300', dot: 'bg-ground-300' })
    for (const code of ['none', 'unsorted']) {
      expect(sliceClasses(code, 3).stroke).not.toContain('caution')
      expect(sliceClasses(code, 3).stroke).not.toContain('critical')
    }
  })

  it('gives a slice that was never drawn the palest ground, not a swatch', () => {
    // A coloured dot beside RM0.00 promises a slice the reader would then hunt for in the ring.
    expect(sliceClasses('health', -1)).toEqual({ stroke: 'stroke-ground-100', dot: 'bg-ground-100' })
  })

  it('never returns a class Tailwind could not have seen', () => {
    // Complete literals only — a class assembled at runtime ships unstyled.
    for (let rank = 0; rank < 8; rank += 1) {
      expect(sliceClasses('food', rank).stroke).toMatch(/^stroke-category-[1-8]-dot$/)
    }
  })
})

describe('the axis labels are numeric and British', () => {
  it('reads a week as its Monday, day then month', () => {
    expect(weekLabel('2026-03-02')).toBe('02/03')
  })

  it('reads a month as month then year', () => {
    expect(monthLabel('2026-07')).toBe('07/2026')
  })

  it('hands back anything it does not recognise, rather than inventing a date', () => {
    expect(weekLabel('')).toBe('')
    expect(monthLabel('nonsense')).toBe('nonsense')
  })
})

describe('has — the page renders by PRESENCE, never by role', () => {
  const payload = { sections: ['money', 'intake'], money: { paid: '1.00' }, intake: null }

  it('is true only when the section is both listed and present', () => {
    expect(has(payload, 'money')).toBe(true)
    expect(has(payload, 'funnel')).toBe(false)
  })

  /* ⚠ `intake: null` IS A REAL ANSWER — "no gift was named, so there is no single round to
   * describe" — and the page must render the section and say so, not silently drop it. */
  it('counts a NULL section as present, because null is an answer', () => {
    expect(has(payload, 'intake')).toBe(true)
  })

  it('says no to an absent, empty or null payload rather than throwing', () => {
    expect(has(null, 'money')).toBe(false)
    expect(has(undefined, 'money')).toBe(false)
    expect(has({}, 'money')).toBe(false)
  })

  it('will not report a section that is LISTED but did not arrive', () => {
    // An empty panel reads as "you have none of these", which is a different claim from
    // "this is not your section".
    expect(has({ sections: ['money'] }, 'money')).toBe(false)
  })
})

describe('bandTone — the band is on the CASE, never on the person', () => {
  it('reserves the warning tones for a clock that has actually run down', () => {
    expect(bandTone('overdue')).toContain('critical')
    expect(bandTone('due_soon')).toContain('caution')
  })

  it('leaves an open case plain — holding a case is the normal state of a volunteer', () => {
    expect(bandTone('open')).toBe('bg-ground-100 text-ground-600')
    expect(bandTone('anything-else')).toBe('bg-ground-100 text-ground-600')
  })
})
