/**
 * @jest-environment jsdom
 *
 * Mobile M8 follow-up (owner's iPhone, 2026-11-04): a viewBox scales its text with it, so the desktop boxes (240-740
 * wide) printed 8-9 unit axis text at 2.8-9.8 px on a 264-326 px phone card. On a phone (below md BY WIDTH) every
 * chart draws in a phone box about as wide as the card, with 11.5-unit text (11-14 px on screen) and at most four
 * month names. From md — and wherever the width is unknown — the caller's box and the old sizes are unchanged.
 */
import { render } from '@testing-library/react'
import { BarChart, LineChart, PHONE_CHART_TEXT } from '../Charts'
import { PHONE_WIDTH_QUERY } from '@/lib/phoneWidth'
import { FULL_AXIS_BOX, PHONE_AXIS_BOX, PHONE_TICKS_MAX } from '@/lib/programmeOverview'

function widthIs(phone: boolean | null) {
  if (phone === null) { delete (window as { matchMedia?: unknown }).matchMedia; return }
  window.matchMedia = ((q: string) => ({
    matches: q === PHONE_WIDTH_QUERY && phone, media: q, addEventListener: () => {}, removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}
afterEach(() => widthIs(null))

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']
const money = () => (
  <BarChart testId="chart-money" label="Money per month" box={FULL_AXIS_BOX}
    series={[{ key: 'released', className: 'fill-brand-shape', values: MONTHS.map((_, i) => (i + 1) * 1000) }]}
    columns={MONTHS} ticks={MONTHS.map((label, index) => ({ index, label }))}
    yAxis={{ label: 'RM', format: (v) => `RM${Math.round(v)}` }} />
)

/** On screen, a viewBox unit is (card width / box width) CSS px. The phone card is 264 px (sandbox frame, 360)
 *  to 326 px (the real page at 390): the text must land between 11 and 14 px across that range. */
const onScreen = (units: number, boxWidth: number, card: number) => (units * card) / boxWidth

it('the phone text and box draw 11-14 px across every phone card width', () => {
  const units = Number(PHONE_CHART_TEXT.match(/\[([\d.]+)px\]/)![1])
  for (const card of [264, 294, 296, 326]) {
    const px = onScreen(units, PHONE_AXIS_BOX.width, card)
    expect(px).toBeGreaterThanOrEqual(11)
    expect(px).toBeLessThanOrEqual(14)
  }
})

/** TD-490: both pictures are always in the markup; CSS shows one. [desktop svg, phone twin]. */
const twins = (c: ParentNode) => Array.from(c.querySelectorAll('svg')) as SVGSVGElement[]
const box = (w: number, h: number) => `0 0 ${w} ${h}`

it('the phone twin has the phone box, 11.5-unit text on every label and at most four month names', () => {
  widthIs(true)
  const { container } = render(money())
  const [, phone] = twins(container)
  expect(phone.getAttribute('viewBox')).toBe(box(PHONE_AXIS_BOX.width, PHONE_AXIS_BOX.height))
  const texts = Array.from(phone.querySelectorAll('text'))
  expect(texts.length).toBeGreaterThan(0)
  for (const t of texts) expect(t.getAttribute('class')).toContain(PHONE_CHART_TEXT)
  const months = MONTHS.filter((m) => texts.some((t) => t.textContent === m))
  expect(months.length).toBeLessThanOrEqual(PHONE_TICKS_MAX)
})

it('TD-490: the first paint already holds both pictures, one hidden by CSS each way, with no width read', () => {
  widthIs(null)   // no matchMedia at all: the markup must not depend on it
  const { container } = render(money())
  const [wide, phone] = twins(container)
  expect(twins(container)).toHaveLength(2)
  expect(wide.getAttribute('class')).toContain('max-md:hidden')
  expect(phone.getAttribute('class')).toContain('md:hidden')
  expect(phone.getAttribute('class')).not.toContain('max-md:hidden')
  expect(wide.getAttribute('viewBox')).toBe(box(FULL_AXIS_BOX.width, FULL_AXIS_BOX.height))
  expect(phone.getAttribute('viewBox')).toBe(box(PHONE_AXIS_BOX.width, PHONE_AXIS_BOX.height))
  // one test id, one element: the twin carries none
  expect(container.querySelectorAll('[data-testid="chart-ticks"]')).toHaveLength(1)
  expect(container.querySelectorAll('[data-testid="chart-bar"]')).toHaveLength(MONTHS.length)
  expect(phone.querySelector('[data-testid]')).toBeNull()
})

it('a line chart has the twin too', () => {
  const { container } = render(
    <LineChart testId="chart-line" label="x" values={[1, 2, 3]} columns={['a', 'b', 'c']}
      yAxis={{ label: 'RM', format: (v) => String(v) }} />)
  const [, phone] = twins(container)
  expect(phone.getAttribute('viewBox')).toBe(box(PHONE_AXIS_BOX.width, PHONE_AXIS_BOX.height))
  for (const t of Array.from(phone.querySelectorAll('text'))) expect(t.getAttribute('class')).toContain(PHONE_CHART_TEXT)
})

it('the desktop picture keeps the caller\'s box, the 8/9-unit text and every month', () => {
  const { container } = render(money())
  const [wide] = twins(container)
  expect(wide.getAttribute('viewBox')).toBe(box(FULL_AXIS_BOX.width, FULL_AXIS_BOX.height))
  expect(wide.querySelectorAll('[data-testid="chart-ticks"] text')).toHaveLength(MONTHS.length)
  expect(wide.querySelector('[data-testid="chart-ticks"] text')!.getAttribute('class')).toContain('text-[9px]')
  expect(wide.querySelector('[data-testid="chart-y-axis"] text')!.getAttribute('class')).toContain('text-[8px]')
  expect(wide.innerHTML).not.toContain(PHONE_CHART_TEXT)
})
