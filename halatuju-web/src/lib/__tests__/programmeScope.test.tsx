/**
 * @jest-environment jsdom
 *
 * Which gift the console is looking at (`lib/programmeScope`).
 *
 * ⚠ EVERY TEST HERE EXISTS BECAUSE OF ONE LIVE DEFECT, FOUND BY THE OWNER ON FIRST USE
 * (2026-09-03). They created a second gift, pressed "Open its settings", and the console showed
 * them the FIRST gift's settings — silently, with the breadcrumb naming the first gift too.
 *
 * The cause was two rules welded into one expression: "drop a code we do not recognise" and
 * "resolve a single gift when nobody has chosen". Each is correct alone. Together, an unrecognised
 * pick fell through the first rule into the second and came out as a DIFFERENT gift. The new gift
 * was unrecognised because it was inactive and the scopes endpoint returned active programmes only
 * — but the endpoint is only half the fix, because the substitution must be impossible however the
 * list is populated.
 *
 * The invariant, stated once: **a pick is honoured, or it resolves to nothing. It is never
 * replaced.**
 */
import { fireEvent, render, screen } from '@testing-library/react'

import { ProgrammeScopeProvider, useProgrammeScope } from '@/lib/programmeScope'

const FLAGSHIP = { code: 'brightpath-flagship', name: 'BrightPath Bursary' }
const SECOND = { code: 'test', name: 'Test Programme' }

/** Renders the resolved state, and offers a button to pick a code the way a screen would. */
function Probe({ pick }: { pick?: string }) {
  const { chosen, programme, ambiguous, choices } = useProgrammeScope()
  return (
    <div>
      <span data-testid="chosen">{chosen || '(none)'}</span>
      <span data-testid="name">{programme?.name || '(none)'}</span>
      <span data-testid="ambiguous">{String(ambiguous)}</span>
      <span data-testid="count">{choices.length}</span>
      <Picker code={pick} />
    </div>
  )
}

function Picker({ code }: { code?: string }) {
  const { select } = useProgrammeScope()
  if (!code) return null
  return <button type="button" onClick={() => select(code)}>pick</button>
}

const mount = (choices: { code: string; name: string }[], pick?: string) =>
  render(
    <ProgrammeScopeProvider choices={choices}>
      <Probe pick={pick} />
    </ProgrammeScopeProvider>,
  )

const chosen = () => screen.getByTestId('chosen').textContent
const name = () => screen.getByTestId('name').textContent

describe('nothing has been chosen yet', () => {
  it('resolves a single gift without asking — production today', () => {
    mount([FLAGSHIP])
    expect(chosen()).toBe('brightpath-flagship')
    expect(screen.getByTestId('ambiguous').textContent).toBe('false')
  })

  it('resolves NOTHING when there are several, rather than picking the first', () => {
    mount([FLAGSHIP, SECOND])
    expect(chosen()).toBe('(none)')
    expect(screen.getByTestId('ambiguous').textContent).toBe('true')
  })

  it('resolves nothing when the caller has no gifts at all', () => {
    mount([])
    expect(chosen()).toBe('(none)')
  })
})

describe('a gift has been chosen', () => {
  it('honours a choice of the FIRST gift too, not only of the new one', () => {
    // Both directions matter: the substitution bug happened to hand back the first gift, so a
    // test that only ever picked the second could pass while the code returned a constant.
    mount([FLAGSHIP, SECOND], 'brightpath-flagship')
    expect(chosen()).toBe('(none)')          // nothing chosen until the press
    fireEvent.click(screen.getByText('pick'))
    expect(chosen()).toBe('brightpath-flagship')
  })

  it('switches to the gift that was picked', () => {
    mount([FLAGSHIP, SECOND], 'test')
    fireEvent.click(screen.getByText('pick'))
    expect(chosen()).toBe('test')
    expect(name()).toBe('Test Programme')
  })
})

describe('⚠ the owner’s defect: a pick we do not recognise', () => {
  // THE REGRESSION TEST. Before the fix this returned 'brightpath-flagship' — the console
  // answering "which gift am I in?" with a gift the person had not opened.
  it('resolves to NOTHING, never to the only gift in the list', () => {
    mount([FLAGSHIP], 'test')
    fireEvent.click(screen.getByText('pick'))
    expect(chosen()).toBe('(none)')
    expect(name()).toBe('(none)')
  })

  it('resolves to nothing rather than the first of several', () => {
    mount([FLAGSHIP, SECOND], 'gone')
    fireEvent.click(screen.getByText('pick'))
    expect(chosen()).toBe('(none)')
  })

  it('recovers the moment the list catches up with the pick', () => {
    // The real sequence: the pick lands before the scopes list has the new gift in it. Once the
    // list arrives, the SAME pick must resolve — a discarded code must not be forgotten.
    const { rerender } = render(
      <ProgrammeScopeProvider choices={[FLAGSHIP]}>
        <Probe pick="test" />
      </ProgrammeScopeProvider>,
    )
    fireEvent.click(screen.getByText('pick'))
    expect(chosen()).toBe('(none)')

    rerender(
      <ProgrammeScopeProvider choices={[FLAGSHIP, SECOND]}>
        <Probe pick="test" />
      </ProgrammeScopeProvider>,
    )
    expect(chosen()).toBe('test')
  })
})

describe('outside the provider', () => {
  it('behaves as it did before this module existed — no gift, no crash', () => {
    render(<Probe />)
    expect(chosen()).toBe('(none)')
    expect(screen.getByTestId('count').textContent).toBe('0')
  })
})
