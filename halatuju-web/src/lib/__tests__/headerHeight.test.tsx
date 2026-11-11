/**
 * @jest-environment jsdom
 *
 * TD-457: the student header publishes its height as `--header-height`, and the saved compare's
 * sticky course-name row sticks at that variable instead of a hard-coded 4.25rem.
 */
import { useRef } from 'react'
import { render } from '@testing-library/react'
import { useHeaderHeight } from '../headerHeight'
import { readWeb } from '@/test/sourceGuard'

function Header() {
  const ref = useRef<HTMLElement>(null)
  useHeaderHeight(ref)
  return <header ref={ref}>h</header>
}

const varNow = () => document.documentElement.style.getPropertyValue('--header-height')

afterEach(() => jest.restoreAllMocks())

it('sets --header-height to the header height and removes it on unmount', () => {
  jest.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(77)
  const view = render(<Header />)
  expect(varNow()).toBe('77px')
  view.unmount()
  expect(varNow()).toBe('')
})

it('AppHeader publishes it and SavedCompare sticks at it', () => {
  expect(readWeb('src/components/AppHeader.tsx', 'the header publishes its height')).toMatch(/useHeaderHeight\(/)
  const compare = readWeb('src/components/saved/SavedCompare.tsx', 'the row sticks under the header')
  expect(compare).toMatch(/top-\[var\(--header-height,/)
})
