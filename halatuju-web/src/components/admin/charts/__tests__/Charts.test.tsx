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
})
