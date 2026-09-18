/**
 * @jest-environment jsdom
 *
 * The console's three chart shapes, rendered.
 *
 * ⚠ THE TESTS HERE ARE WRITTEN FROM THE HARM, and there are three harms:
 *
 *  * **A raw hex colour.** The theme guards scan SOURCE for `#rrggbb`, and colour hides in SVG
 *    attributes — `fill="#2563eb"` is invisible to a class-based scan and survives every theme
 *    swap unchanged, so it would look right in light mode and wrong in dark for ever. This file
 *    reads the RENDERED markup instead, which is the only place a computed colour can surface.
 *  * **A chart with no numbers.** A value that exists only as a pixel height cannot be read
 *    aloud, quoted in an email, or checked against the Payments footer. Every chart renders its
 *    figures as text beneath it, and that is asserted as TEXT, not as a title attribute.
 *  * **A chart with no name.** `role="img"` without an `aria-label` is an unlabelled image: a
 *    screen reader announces "graphic" and stops.
 */
import type { ReactElement } from 'react'
import { render, screen, within } from '@testing-library/react'

import { BarChart, Donut, LineChart } from '../Charts'

const FIGURES = [{ label: '02/03', value: '15' }, { label: '09/03', value: '36' }]

/** Everything a chart puts on screen, as one string of markup. */
function markup(ui: ReactElement): string {
  const { container } = render(ui)
  return container.innerHTML
}

describe('BarChart', () => {
  const bars = (
    <BarChart
      testId="chart-bars"
      label="Applications received per week"
      series={[{ key: 'count', className: 'fill-brand-shape', values: [15, 36] }]}
      columns={['02/03', '09/03']}
      figures={FIGURES}
    />
  )

  it('is a named image, not an unlabelled graphic', () => {
    render(bars)
    const img = screen.getByRole('img', { name: 'Applications received per week' })
    expect(img).not.toBeNull()
    expect(img.tagName.toLowerCase()).toBe('svg')
  })

  it('renders its figures as TEXT beneath the shape', () => {
    render(bars)
    const list = screen.getByTestId('chart-bars-figures')
    expect(within(list).getAllByRole('listitem').length).toBe(2)
    expect(list.textContent).toContain('02/03')
    expect(list.textContent).toContain('36')
  })

  it('draws one rect per column, in the class the caller named', () => {
    const { container } = render(bars)
    const rects = container.querySelectorAll('rect')
    expect(rects.length).toBe(2)
    expect((container.querySelector('g') as Element).getAttribute('class'))
      .toBe('fill-brand-shape')
  })

  it('draws the optional line, and only when one is given', () => {
    const plain = render(bars).container
    expect(plain.querySelector('polyline')).toBeNull()
    const { container } = render(
      <BarChart
        testId="chart-money" label="Money released and spent per month"
        series={[{ key: 'released', className: 'fill-brand-shape', values: [10, 0] }]}
        line={{ className: 'stroke-ground-600', values: [10, -5] }}
        columns={['05/2026', '06/2026']} figures={FIGURES}
      />)
    expect(container.querySelector('polyline')).not.toBeNull()
  })

  it('has no raw hex colour anywhere in what it renders', () => {
    const html = markup(bars)
    expect(html.indexOf('fill="#')).toBe(-1)
    expect(html.indexOf('stroke="#')).toBe(-1)
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  /* ⚠ A BAR IS ITS OWN HIT TARGET: the `<title>` sits inside the rect. The line's points get
   * invisible circles, as on `LineChart`. With no figures, no list is rendered at all. */
  it('answers bars and line points on hover, draws a y-axis, and prints no empty list', () => {
    const { container } = render(
      <BarChart testId="chart-hover" label="Money released and spent per month"
        series={[
          { key: 'released', className: 'fill-brand-shape', values: [100, 250], titles: ['RM100.00', 'RM250.00'] },
          { key: 'spent', className: 'fill-ground-300', values: [40, 90], titles: ['RM40.00', 'RM90.00'] },
        ]}
        line={{ className: 'stroke-ground-600', values: [60, 220], titles: ['RM60.00', 'RM220.00'] }}
        columns={['Jul', 'Aug']} ticks={[{ index: 0, label: 'Jul' }, { index: 1, label: 'Aug' }]}
        yAxis={{ label: 'RM', format: (v) => `RM${Math.round(v)}` }}
        box={{ width: 740, height: 160, top: 10, bottom: 24, side: 12, left: 64 }} />)
    const bars = container.querySelectorAll('[data-testid="chart-bar"]')
    expect(bars.length).toBe(4)
    expect(bars[1].querySelector('title')?.textContent).toBe('RM250.00')
    expect(bars[2].querySelector('title')?.textContent).toBe('RM40.00')
    const points = container.querySelectorAll('[data-testid="chart-point"]')
    expect(points.length).toBe(2)
    expect(points[1].querySelector('title')?.textContent).toBe('RM220.00')
    const axis = container.querySelector('[data-testid="chart-y-axis"]') as Element
    expect(axis.textContent).toContain('RM250')   // the bars' scale, not the line's
    expect(axis.textContent).toContain('RM125')
    expect(container.querySelector('[data-testid="chart-hover-figures"]')).toBeNull()
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  it('names every column when given ticks, and drops the end labels', () => {
    const { container } = render(
      <BarChart testId="chart-months" label="Money released and spent per month"
        series={[{ key: 'released', className: 'fill-brand-shape', values: [10, 20, 5] }]}
        columns={['Jun', 'Jul', 'Aug']}
        ticks={[{ index: 0, label: 'Jun' }, { index: 1, label: 'Jul' }, { index: 2, label: 'Aug' }]}
        figures={[]} />)
    const ticks = container.querySelector('[data-testid="chart-ticks"]') as Element
    expect(ticks.querySelectorAll('text').length).toBe(3)
    // One label per column, and only one: the end-label system is not also drawn.
    expect(container.querySelectorAll('text').length).toBe(3)
  })
})

describe('LineChart', () => {
  const line = (
    <LineChart
      testId="chart-line" label="Average spend per student per week"
      values={[19.4, 31.2, 24]} columns={['04/05', '18/05']}
      figures={[{ label: '04/05', value: 'RM19.40' }]}
    />
  )

  it('is named, and carries its figures as text', () => {
    render(line)
    expect(screen.getByRole('img', { name: 'Average spend per student per week' })).not.toBeNull()
    expect(screen.getByTestId('chart-line-figures').textContent).toContain('RM19.40')
  })

  it('marks the latest point so "where are we now" is answerable at a glance', () => {
    const { container } = render(line)
    expect(container.querySelectorAll('circle').length).toBe(1)
  })

  /* ⚠ THE ZERO LINE APPEARS ONLY WHEN SOMETHING IS NEGATIVE. Otherwise it lands on the axis and
   * two strokes on one pixel just read as a heavier baseline. */
  it('draws a zero line for a series that goes below zero, and not otherwise', () => {
    const positive = render(line).container
    expect(positive.querySelectorAll('line').length).toBe(1)
    const { container } = render(
      <LineChart testId="chart-gap" label="Still in wallets" values={[10, -5]}
        columns={['05/2026', '06/2026']} figures={[]} />)
    expect(container.querySelectorAll('line').length).toBe(2)
  })

  it('has no raw hex colour anywhere in what it renders', () => {
    const html = markup(line)
    expect(html.indexOf('fill="#')).toBe(-1)
    expect(html.indexOf('stroke="#')).toBe(-1)
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  /* ⚠ TICKS REPLACE THE END LABELS, they do not join them — two systems of labels on one axis
   * collide at the first column. And a y-axis names its unit and its two exact values (the top
   * IS the largest value, the baseline IS the smallest), nothing rounded in between. */
  it('draws named month ticks instead of end labels, and a y-axis when asked', () => {
    const { container } = render(
      <LineChart testId="chart-axes" label="Average spend per student per week"
        values={[19.4, 31.2, 24]} columns={['04/05', '11/05', '01/06']}
        ticks={[{ index: 0, label: 'May' }, { index: 2, label: 'Jun' }]}
        yAxis={{ label: 'RM per student', format: (v) => `RM${Math.round(v)}` }}
        box={{ width: 240, height: 120, top: 10, bottom: 18, side: 10, left: 46 }}
        figures={[{ label: 'Whole period', value: 'RM230.22' }]} />)
    const ticks = container.querySelector('[data-testid="chart-ticks"]') as Element
    expect(ticks.querySelectorAll('text').length).toBe(2)
    expect(ticks.textContent).toBe('MayJun')
    expect(container.textContent).not.toContain('04/05')
    const axis = container.querySelector('[data-testid="chart-y-axis"]') as Element
    expect(axis.textContent).toContain('RM per student')
    expect(axis.textContent).toContain('RM31')   // the top of the plot is the largest value
    expect(axis.textContent).toContain('RM16')   // the middle is their mean (31.2 / 2 = 15.6)
    expect(axis.textContent).toContain('RM0')    // the baseline is zero for an all-positive line
    // Two gridlines, top and middle — plus the baseline, three lines in all.
    expect(axis.querySelectorAll('line').length).toBe(2)
    expect(container.querySelectorAll('line').length).toBe(3)
    const html = container.innerHTML
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  /* ⚠ HOVER TARGETS, NOT MARKS. One invisible circle per point carrying the browser's own
   * `<title>` — the one-week answer the owner asked for, with no state and no positioning code.
   * The visible marks are unchanged: the latest point still has its one dot. */
  it('gives every point a title to show on hover, and draws no extra visible mark', () => {
    const { container } = render(
      <LineChart testId="chart-hover" label="Average spend per student per week"
        values={[19.4, 31.2, 24]} columns={['04/05', '11/05', '18/05']}
        pointTitles={['04/05: RM19.40', '11/05: RM31.20', '18/05: RM24.00']}
        figures={[]} />)
    const hits = container.querySelectorAll('[data-testid="chart-point"]')
    expect(hits.length).toBe(3)
    expect(hits[1].querySelector('title')?.textContent).toBe('11/05: RM31.20')
    expect(hits[0].getAttribute('class')).toBe('fill-transparent')
    // Without titles, no hit targets at all — and the latest-point dot is the only circle.
    const plain = render(
      <LineChart testId="chart-plain" label="x" values={[1, 2]} columns={['a', 'b']} figures={[]} />)
    expect(plain.container.querySelectorAll('[data-testid="chart-point"]').length).toBe(0)
    expect(plain.container.querySelectorAll('circle').length).toBe(1)
  })
})

describe('Donut', () => {
  const rows = [
    { code: 'food', label: 'Food & drink', display: 'RM3,738.00', total: '3738.00' },
    { code: 'health', label: 'Health & pharmacy', display: 'RM0.00', total: '0.00' },
    { code: 'unsorted', label: 'Could not be sorted', display: 'RM0.00', total: '0.00' },
    { code: 'none', label: 'Not yet sorted', display: 'RM4,006.00', total: '4006.00' },
  ]
  const donut = <Donut testId="chart-donut" label="Spending by category" rows={rows} />

  it('is named, and lists EVERY row including the ones at zero', () => {
    render(donut)
    expect(screen.getByRole('img', { name: 'Spending by category' })).not.toBeNull()
    const list = screen.getByTestId('chart-donut-figures')
    expect(within(list).getAllByRole('listitem').length).toBe(4)
    expect(list.textContent).toContain('Health & pharmacy')
    expect(list.textContent).toContain('RM0.00')
  })

  /* ⚠ THE RING AND THE LIST ANSWER DIFFERENT QUESTIONS. Two rows have money, so two arcs are
   * drawn on top of the track — a zero-length arc would be invisible and would spend a colour the
   * next real category then could not have. */
  it('draws an arc only for the slices that actually have money', () => {
    const { container } = render(donut)
    // one track circle + one arc per non-zero slice
    expect(container.querySelectorAll('circle').length).toBe(3)
  })

  it('gives the two unknown states ground tokens, never a category swatch', () => {
    const html = markup(donut)
    expect(html).toContain('bg-ground-300')       // `unsorted`, in the legend
    expect(html).toContain('bg-ground-200')       // `none`, in the legend
    // `none` DOES carry money here, so it is drawn — and it is still a ground stroke, never a
    // swatch: a warning-free, colour-free slice for "nobody has looked at this yet".
    expect(html).toContain('stroke-ground-200')
  })

  it('has no raw hex colour anywhere in what it renders', () => {
    const html = markup(donut)
    expect(html.indexOf('fill="#')).toBe(-1)
    expect(html.indexOf('stroke="#')).toBe(-1)
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  /* ⚠ THE TOTAL IS THE CALLER'S FIGURE, printed as given — the ring never sums its own rows. */
  it('prints the total beneath the ring when given one, and nothing when not', () => {
    render(<Donut testId="chart-total" label="Spending by category" rows={rows}
      total={{ label: 'Total spending', value: 'RM7,744.00' }} />)
    const total = screen.getByTestId('chart-total-total')
    expect(total.textContent).toContain('Total spending')
    expect(total.textContent).toContain('RM7,744.00')
    const { container } = render(donut)
    expect(container.querySelector('[data-testid="chart-donut-total"]')).toBeNull()
  })
})
