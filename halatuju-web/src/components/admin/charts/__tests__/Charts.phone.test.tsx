/**
 * @jest-environment jsdom
 *
 * Mobile M8 follow-up (owner's iPhone, 2026-11-04): a viewBox scales its text with it, so the desktop boxes (240-740
 * wide) printed 8-9 unit axis text at 2.8-9.8 px on a 264-326 px phone card. On a phone (below md BY WIDTH) every
 * chart draws in a phone box about as wide as the card, with 11.5-unit text (11-14 px on screen) and at most four
 * month names. From md — and wherever the width is unknown — the caller's box and the old sizes are unchanged.
 */
import { act, render } from '@testing-library/react'
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

it('a phone gets the phone box, 11.5-unit text on every label and at most four month names', async () => {
  widthIs(true)
  const { container } = render(money())
  await act(async () => {})
  expect(container.querySelector('svg')!.getAttribute('viewBox')).toBe(`0 0 ${PHONE_AXIS_BOX.width} ${PHONE_AXIS_BOX.height}`)
  const texts = Array.from(container.querySelectorAll('text'))
  expect(texts.length).toBeGreaterThan(0)
  for (const t of texts) expect(t.getAttribute('class')).toContain(PHONE_CHART_TEXT)
  expect(container.querySelectorAll('[data-testid="chart-ticks"] text').length).toBeLessThanOrEqual(PHONE_TICKS_MAX)
})

it('a line chart swaps too', async () => {
  widthIs(true)
  const { container } = render(
    <LineChart testId="chart-line" label="x" values={[1, 2, 3]} columns={['a', 'b', 'c']}
      yAxis={{ label: 'RM', format: (v) => String(v) }} />)
  await act(async () => {})
  expect(container.querySelector('svg')!.getAttribute('viewBox')).toBe(`0 0 ${PHONE_AXIS_BOX.width} ${PHONE_AXIS_BOX.height}`)
  for (const t of Array.from(container.querySelectorAll('text'))) expect(t.getAttribute('class')).toContain(PHONE_CHART_TEXT)
})

it('from md, and with no matchMedia, the caller\'s box, the 8/9-unit text and every month are unchanged', async () => {
  for (const w of [false, null] as const) {
    widthIs(w)
    const { container, unmount } = render(money())
    await act(async () => {})
    expect(container.querySelector('svg')!.getAttribute('viewBox')).toBe(`0 0 ${FULL_AXIS_BOX.width} ${FULL_AXIS_BOX.height}`)
    expect(container.querySelectorAll('[data-testid="chart-ticks"] text')).toHaveLength(MONTHS.length)
    expect(container.querySelector('[data-testid="chart-ticks"] text')!.getAttribute('class')).toContain('text-[9px]')
    expect(container.querySelector('[data-testid="chart-y-axis"] text')!.getAttribute('class')).toContain('text-[8px]')
    expect(container.innerHTML).not.toContain(PHONE_CHART_TEXT)
    unmount()
  }
})
