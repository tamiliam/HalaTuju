/**
 * The arithmetic behind the Programme Overview's charts (node — no DOM, by design).
 *
 * ⚠ THE GEOMETRY IS TESTED HERE RATHER THAN THROUGH A RENDERED SVG, because the half of a chart
 * that can be silently wrong is the half made of numbers: a bar that is 3px too short still looks
 * like a bar, and a donut whose arcs do not sum to the ring still looks like a donut. What the
 * component test next door proves is that the tokens and the labels reached the markup.
 */
import {
  FULL_BOX, SMALL_AXIS_BOX, SMALL_BOX, WIDE_BOX, bandTone, barLayout, columnX, donutArcs, has,
  lineLayout, monthOf, monthTicks, num, plotLeft, rm, sliceClasses, thinTicks, weekLabel,
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

describe('the week label is numeric and British', () => {
  it('reads a week as its Monday, day then month', () => {
    expect(weekLabel('2026-03-02')).toBe('02/03')
  })

  it('hands back anything it does not recognise, rather than inventing a date', () => {
    expect(weekLabel('')).toBe('')
  })
})

describe('month ticks — the axis is labelled in months whatever the columns are', () => {
  const name = (m: number) => ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m]

  it('reads the month out of a month key and out of a week date alike', () => {
    expect(monthOf('2026-07')).toBe(7)
    expect(monthOf('2026-07-06')).toBe(7)
    expect(monthOf('nonsense')).toBe(0)
    expect(monthOf('2026-13')).toBe(0)
  })

  /* ⚠ ONE TICK PER MONTH CHANGE, at the first column of that month — fifty weekly columns
   * become a dozen labels, which is the whole point (owner: "imagine the chart twelve months in"). */
  it('puts one tick at the first column of each month, and always one at the start', () => {
    const weeks = ['2026-06-29', '2026-07-06', '2026-07-13', '2026-07-27', '2026-08-03', '2026-08-10']
    expect(monthTicks(weeks, name)).toEqual([
      { index: 0, label: 'Jun' }, { index: 1, label: 'Jul' }, { index: 4, label: 'Aug' },
    ])
    expect(monthTicks(['2026-07-06', '2026-07-13'], name)).toEqual([{ index: 0, label: 'Jul' }])
    expect(monthTicks([], name)).toEqual([])
  })

  it('skips a column it cannot read rather than labelling it nonsense', () => {
    expect(monthTicks(['x', '2026-07-06'], name)).toEqual([{ index: 1, label: 'Jul' }])
  })

  it('thins a long run of ticks evenly and keeps the first', () => {
    const many = Array.from({ length: 30 }, (_, i) => ({ index: i, label: `m${i}` }))
    const thinned = thinTicks(many, 12)
    expect(thinned.length).toBeLessThanOrEqual(12)
    expect(thinned[0]).toEqual({ index: 0, label: 'm0' })
    expect(thinned[1]).toEqual({ index: 3, label: 'm3' })
    expect(thinTicks(many.slice(0, 4), 12)).toEqual(many.slice(0, 4))
  })
})

describe('columnX — one x for a bar and a point in the same column', () => {
  it('centres each column across the plot, inside the left margin when there is one', () => {
    const box = { width: 240, height: 120, top: 10, bottom: 18, side: 10, left: 46 }
    expect(plotLeft(box)).toBe(46)
    expect(plotLeft(SMALL_BOX)).toBe(SMALL_BOX.side)
    // Two columns across 240 − 46 − 10 = 184px: centres at 46 + 46 and 46 + 138.
    expect(columnX(0, 2, box)).toBe(92)
    expect(columnX(1, 2, box)).toBe(184)
    expect(columnX(0, 0, box)).toBe(46)
  })

  it('is the x the line layout uses, so a tick lands under its point', () => {
    const { points } = lineLayout([1, 2, 3], SMALL_AXIS_BOX)
    expect(points[1].x).toBe(columnX(1, 3, SMALL_AXIS_BOX))
    // …and bars start inside the same margin.
    const { bars } = barLayout([[1, 2]], SMALL_AXIS_BOX)
    expect(bars[0][0].x).toBeGreaterThanOrEqual(SMALL_AXIS_BOX.left as number)
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
