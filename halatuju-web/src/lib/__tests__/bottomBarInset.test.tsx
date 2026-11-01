/**
 * @jest-environment jsdom
 *
 * Mobile M3: a sticky bottom bar tells the toast its height (`--bottom-bar`), re-measures when it
 * appears later than its owner, and takes the variable away when it goes.
 */
import { useRef } from 'react'
import { render } from '@testing-library/react'
import { useBottomBarInset } from '../bottomBarInset'

function Bar({ shown }: { shown: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useBottomBarInset(ref, shown)
  return shown ? <div ref={ref}>bar</div> : null
}

const varNow = () => document.documentElement.style.getPropertyValue('--bottom-bar')

beforeEach(() => {
  jest.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(72)
})
afterEach(() => jest.restoreAllMocks())

it('sets --bottom-bar to the bar height, and removes it on unmount', () => {
  const view = render(<Bar shown />)
  expect(varNow()).toBe('72px')
  view.unmount()
  expect(varNow()).toBe('')
})

it('a bar that appears LATER (the first tick) is measured when it appears', () => {
  const view = render(<Bar shown={false} />)
  expect(varNow()).toBe('')
  view.rerender(<Bar shown />)
  expect(varNow()).toBe('72px')
  view.rerender(<Bar shown={false} />)
  expect(varNow()).toBe('')
})
