/**
 * @jest-environment jsdom
 *
 * TD-457: the student header publishes its height as `--header-height`, and the saved compare's
 * sticky course-name row sticks at that variable instead of a hard-coded 4.25rem.
 */
import { render } from '@testing-library/react'
import { useHeaderHeight } from '../headerHeight'
import { readWeb } from '@/test/sourceGuard'

function Row() {
  useHeaderHeight()
  return <header data-app-header>h</header>
}

const varNow = () => document.documentElement.style.getPropertyValue('--header-height')

afterEach(() => jest.restoreAllMocks())

it('sets --header-height to the marked header height and removes it on unmount', () => {
  jest.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(77)
  const view = render(<Row />)
  expect(varNow()).toBe('77px')
  view.unmount()
  expect(varNow()).toBe('')
})

it('AppHeader carries the mark, and SavedCompare measures it and sticks at it', () => {
  expect(readWeb('src/components/AppHeader.tsx', 'the header publishes its height')).toMatch(/data-app-header/)
  const compare = readWeb('src/components/saved/SavedCompare.tsx', 'the row sticks under the header')
  expect(compare).toMatch(/useHeaderHeight\(\)/)
  expect(compare).toMatch(/top-\[var\(--header-height,/)
})
